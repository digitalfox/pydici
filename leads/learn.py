# coding: utf-8

"""
Module that handle predictive state of a lead
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import date, timedelta
import re
import zlib
import pickle
import itertools
from celery import shared_task

HAVE_SCIKIT = True
try:
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import MinMaxScaler
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.neighbors import NearestNeighbors
    from sklearn.pipeline import Pipeline
    from sklearn.linear_model import SGDClassifier
    from sklearn.model_selection import GridSearchCV, cross_val_score, train_test_split
    from sklearn.metrics import confusion_matrix, classification_report
    import numpy as np
except ImportError:
    HAVE_SCIKIT = False

from django.db.models import Count, Sum, Min, Max, Avg
from django.core.cache import cache
from django.db.models.query import QuerySet

from leads.models import Lead, StateProba
from taggit.models import Tag
from billing.models import ClientBill
from crm.models import Client
from staffing.models import Consultant

STATES = {"WON": 1, "LOST": 2, "FORGIVEN": 3}
INV_STATES = dict([(v, k) for k, v in list(STATES.items())])

TAG_MODEL_CACHE_KEY = "PYDICI_LEAD_LEARN_TAGS_MODEL"
STATE_MODEL_CACHE_KEY = "PYDICI_LEAD_LEARN_STATE_MODEL"
SIMILARITY_MODEL_CACHE_KEY = "PYDICI_LEAD_SIMILARITY_MODEL"
SIMILARITY_LEADS_IDS_CACHE_KEY = "PYDICI_LEAD_SIMILARITY_LEADS_IDS"
SIMILARITY_LEADS_SALES_SCALER_CACHE_KEY = "PYDICI_LEAD_SIMILARITY_SALES_SCALER"

FR_STOP_WORDS = """alors au aucun aussi autre avant avec avoir bon car ce cela ces ceux chaque ci comme comment
 dans des du dedans dehors depuis devrait doit donc dos début elle elles en encore essai est et eu fait faites fois
 font hors ici il ils je juste la le les leur là ma maintenant mais mes mine moins mon mot même ni nommés notre nous
 ou où par parce pas peut peu plupart pour pourquoi quand que quel quelle quelles quels qui sa sans ses seulement
 si sien son sont sous soyez sujet sur ta tandis tellement tels tes ton tous tout trop très tu voient vont votre vous
 vu ça étaient état étions été être un une de ce cette ces ceux"""


def pairwise(iterable):
    """s -> (s0,s1), (s1,s2), (s2, s3), ...
    # TODO: included in itertools in python 3.11"""
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)

############# Features extraction ##########################

def get_lead_state_data(lead):
    """Get features and target of given lead. Raise Exception if lead data cannot be extracted (ie. incomplete)"""
    feature = {}
    feature["responsible"] = str(lead.responsible)
    if lead.responsible:
        feature["responsible_subsidiary"] = str(lead.responsible.company)
        feature["responsible_manager"] = str(lead.responsible.manager)
        feature["responsible_profil"] = str(lead.responsible.profil)
        feature["responsible_team_size"] = lead.responsible.team().count()
        feature["responsible_is_company_business_owner"] = int(
            lead.client.organisation.company.businessOwner == lead.responsible)
    feature["subsidiary"] = str(lead.subsidiary)
    feature["client_orga"] = str(lead.client.organisation)
    feature["client_company"] = str(lead.client.organisation.company)
    bills = ClientBill.objects.filter(lead__client__organisation__company=lead.client.organisation.company)
    feature["client_company_last_year_sales"] = float(list(bills.filter(creation_date__lt=lead.creation_date,
                                                                        creation_date__gt=(lead.creation_date - timedelta(360)))
                                                           .aggregate(Sum("amount")).values())[0] or 0)
    feature["client_company_last_year_no_sales"] = int(feature["client_company_last_year_sales"] == 0)
    feature["client_company_last_three_year_sales"] = float(list(bills.filter(creation_date__lt=lead.creation_date,
                                                                              creation_date__gt=(lead.creation_date - timedelta(360 * 3)))
                                                                 .aggregate(Sum("amount")).values())[0] or 0)
    feature["client_contact"] = str(lead.client.contact)
    feature["client_contact_function"] = str(lead.client.contact.function if lead.client.contact and lead.client.contact.function else "Undefined")
    feature["client_contact_num_client"] = Client.objects.filter(contact=lead.client.contact).count()
    feature["no_client_contact"] = int(lead.client.contact is None)
    feature["client_contact_count"] = Lead.objects.filter(client__contact=lead.client.contact,
                                                          creation_date__lt=lead.creation_date).count()
    feature["client_company_business_owner"] = str(lead.client.organisation.company.businessOwner)
    feature["client_company_business_sector"] = str(lead.client.organisation.business_sector)
    if lead.start_date:
        feature["lifetime"] = max(0, (lead.start_date - lead.creation_date.date()).days)

    previous_recent_leads = Lead.objects.filter(creation_date__lt=lead.creation_date,
                                                creation_date__gt=lead.creation_date-timedelta(365*2))
    if lead.sales:
        feature["sales"] = float(lead.sales)
    else:
        # Use client average if available, else default to subsidiary average
        feature["sales"] = previous_recent_leads.filter(client=lead.client).aggregate(Avg("sales"))["sales__avg"]
        if not feature["sales"]:
            feature["sales"] = previous_recent_leads.filter(subsidiary=lead.subsidiary).aggregate(Avg("sales"))["sales__avg"] or 0
        feature["sales"] = float(feature["sales"])
    feature["subsidiary_avg_sales_delta"] = previous_recent_leads.filter(subsidiary=lead.subsidiary).aggregate(Avg("sales"))["sales__avg"]
    feature["subsidiary_avg_sales_delta"] = feature["sales"] - float(feature["subsidiary_avg_sales_delta"] or 0)
    feature["client_avg_sales_delta"] = previous_recent_leads.filter(client=lead.client).aggregate(Avg("sales"))["sales__avg"]
    feature["client_avg_sales_delta"] = feature["sales"] - float(feature["client_avg_sales_delta"] or 0)
    feature["business_sector_avg_sales_delta"] = previous_recent_leads.filter(client__organisation__business_sector=lead.client.organisation.business_sector).aggregate(Avg("sales"))["sales__avg"]
    feature["business_sector_avg_sales_delta"] = feature["sales"] - float(feature["business_sector_avg_sales_delta"] or 0)
    if lead.business_broker:
        feature["broker_company"] = str(lead.business_broker.company)
        feature["broker_count"] = Lead.objects.filter(business_broker=lead.business_broker,
                                                      creation_date__lt=lead.creation_date).count()
        feature["broker_first_lead"] = int(feature["broker_count"] == 0)
    if lead.paying_authority:
        feature["paying_authority_count"] = Lead.objects.filter(paying_authority=lead.paying_authority,
                                                                creation_date__lt=lead.creation_date).count()
        feature["paying_authority_company"] = str(lead.paying_authority.company)
    client_leads = lead.client.lead_set.all().order_by("creation_date")
    feature["lead_client_rank"] = list(client_leads).index(lead)
    feature["first_lead"] = int(feature["lead_client_rank"] == 0)
    feature["leads_last_year"] = client_leads.filter(creation_date__lt=lead.creation_date,
                                                     creation_date__gt=(lead.creation_date - timedelta(360))).count()
    feature["leads_last_three_year"] = client_leads.filter(creation_date__lt=lead.creation_date,
                                                           creation_date__gt=(lead.creation_date - timedelta(360 * 3))).count()
    for timespan in (60, 120):
        feature["nb_leads_active_%s_before" % timespan] = Lead.objects.filter(mission__timesheet__working_date__gt=(lead.creation_date-timedelta(timespan)),
                                                                              mission__timesheet__working_date__lt=lead.creation_date,
                                                                              client=lead.client).distinct().count()
    client_working_consultants = Consultant.objects.filter(timesheet__mission__lead__client=lead.client,
                                                           timesheet__working_date__lt=lead.creation_date).distinct()
    feature["client_working_consultants"] = client_working_consultants.count()
    feature["responsible_already_work_for_client"] = lead.responsible in client_working_consultants
    feature["staf_size"] = lead.staffing.count()
    known_staf = 0
    for staf in lead.staffing.all():
        feature["staffing_%s" % staf.trigramme] = "yes"
        if staf in client_working_consultants:
            known_staf +=1
    if feature["staf_size"] > 0:
        feature["staf_known"] = known_staf / feature["staf_size"]
    for tag in lead.tags.all():
        feature["tag_%s" % tag.slug] = "yes"
    history = lead.history.filter(timestamp__lte=(lead.start_date or date.today()))
    feature["history_changes"] = history.count()
    if feature["history_changes"] > 1:
        history_boundaries = history.aggregate(Min("timestamp"), Max("timestamp"))
        feature["history_length"] = (history_boundaries["timestamp__max"] - history_boundaries["timestamp__min"]).days
        feature["history_actor_count"] = history.aggregate(Count("actor"))["actor__count"]
        history_timestamps = [c.timestamp for c in history]
        if len(history_timestamps) > 1:
            feature["history_mean_time_bet_changes"] = np.median(([(a - b).total_seconds() for a, b in pairwise(history_timestamps)]))

    return feature, lead.state


def extract_leads_state(leads):
    """Extract leads features and targets for state learning"""
    features = []
    targets = []
    if isinstance(leads, QuerySet):
        leads = leads.select_related("subsidiary", "client", "client__organisation", "client__organisation__company",
                                     "responsible", "responsible__company", "responsible__manager", "business_broker",
                                     "paying_authority")
        leads = leads.prefetch_related("tags")
    for lead in leads:
        try:
            feature, target = get_lead_state_data(lead)
            features.append(feature)
            targets.append(target)
        except Exception as e:
            print("Cannot process lead %s (%s)" % (lead.id, e))
    return features, targets


def get_lead_similarity_data(lead):
    """Get features of given lead to compute its similarity with others. Raise Exception if lead data cannot be extracted (ie. incomplete)"""
    feature = {"subsidiary": str(lead.subsidiary), "sales": float(lead.sales or 0)}
    for tag in lead.tags.all():
        feature["tag_%s" % tag.slug] = "yes"
    return feature


def extract_leads_similarity(leads, normalizer):
    """Extract leads features for similarity learning"""
    features = []
    sales = []
    for lead in leads:
        d = get_lead_similarity_data(lead)
        sales.append([d["sales"], ])
        features.append(d)

    sales = normalizer.fit_transform(sales)

    for feature, sale in zip(features, sales):
        feature["sales"] = sale[0]

    return features, normalizer


def process_target(targets):
    return [STATES[i] for i in targets]


def get_lead_tag_data(lead):
    """Extract lead data needed to predict tag"""
    return " ".join([str(lead.client.organisation), str(lead.responsible),
                     str(lead.subsidiary), str(lead.name),
                     str(lead.staffing_list()), str(lead.description)])


def extract_leads_tag(leads, include_leads=False):
    """Extract leads features and targets for tag learning
    @:param include_leads : add leads id at the begining of features for model testing purpose"""
    features = []
    targets = []
    if isinstance(leads, QuerySet):
        leads = leads.select_related("responsible", "client__organisation", "subsidiary")
    for lead in leads:
        lead_info = get_lead_tag_data(lead)
        for tag in lead.tags.all():
            targets.append(str(tag))
            if include_leads:
                features.append("%s %s" % (lead.id, lead_info))
            else:
                features.append(lead_info)
    return features, targets


############# Model definition ##########################
def get_state_model():
    model = Pipeline([("vect", DictVectorizer()), ("clf", RandomForestClassifier(max_features=None,
                                                                                 min_samples_split=2,
                                                                                 min_samples_leaf=5,
                                                                                 criterion='entropy',
                                                                                 n_estimators=300,
                                                                                 class_weight="balanced"))])
    return model


def get_tag_model():
    model = Pipeline([("vect", TfidfVectorizer(stop_words=FR_STOP_WORDS.split(), min_df=2, sublinear_tf=False)),
                      ("clf", SGDClassifier(loss="log_loss", penalty="l1", max_iter=1000, tol=0.01))])
    return model


def get_similarity_model():
    model = Pipeline([("vect", DictVectorizer()), ("neigh", NearestNeighbors(n_neighbors=6))])
    return model


############# Model evaluation ##########################
def test_state_model():
    """Test state model accuracy"""
    leads = Lead.objects.filter(state__in=list(STATES.keys()))
    features, targets = extract_leads_state(leads)
    model = get_state_model()
    model.fit(features, process_target(targets))
    scores = cross_val_score(model, features, process_target(targets), cv=3)
    print(("Score : %0.2f (+/- %0.2f)" % (scores.mean(), scores.std() * 2)))
    return scores.mean()


def eval_state_model(model=None, verbose=True):
    """Display confusion matrix and classif report state model"""
    leads = Lead.objects.filter(state__in=list(STATES.keys()))
    features, targets = extract_leads_state(leads)
    X_train, X_test, y_train, y_test = train_test_split(features, process_target(targets), test_size=0.3)
    if model is None:
        model = get_state_model()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    if verbose:
        print(confusion_matrix(y_test, y_pred))
        print(classification_report(y_test, y_pred))
    feature_names = model.named_steps["vect"].get_feature_names_out()
    coef = model.named_steps["clf"].feature_importances_
    max_coef = max(coef)
    coef = [round(i * 100 / max_coef) for i in coef]
    top = list(zip(feature_names, coef))
    top.sort(key=lambda x: x[1], reverse=True)
    if verbose:
        for i, j in top[:30]:
            print("%s\t\t=> %s" % (i, j))
    m = pickle.dumps(model, protocol=5)
    if verbose:
        print("size %s - compressed %s" % (len(m) / (1024 * 1024), len(zlib.compress(m, level=1)) / (1024 * 1024)))
    return model


def test_tag_model():
    """Test tag model accuracy"""
    leads = Lead.objects.annotate(n_tags=Count("tags")).filter(n_tags__gte=2)
    test_features, test_targets = extract_leads_tag(leads, include_leads=True)
    model = get_tag_model()
    model.fit(test_features, test_targets)
    scores = cross_val_score(model, test_features, test_targets, scoring=score_tag_lead, cv=3)
    m = pickle.dumps(model, protocol=5)
    print("size %s - compressed %s" % (len(m) / (1024 * 1024), len(zlib.compress(m, level=1)) / (1024 * 1024)))
    print(("Score : %0.2f (+/- %0.2f)" % (scores.mean(), scores.std() * 2)))
    return scores.mean()


def grid_cv_tag_model():
    """Perform a grid search cross validation to find best parameters"""
    parameters = {'clf__alpha': (0.1, 0.01, 0.001, 0.0001, 1e-05),
                  'clf__loss': ('log_loss', 'modified_huber', 'squared_hinge'),
                  'clf__penalty': ('none', 'l2', 'l1', 'elasticnet'),
                  'vect__min_df': (1, 2, 3, 4, 5),
                  'vect__norm': ('l1', 'l2'),
                  'vect__sublinear_tf': (True, False),
                  }

    learn_leads = Lead.objects.annotate(n_tags=Count("tags")).filter(n_tags__gte=2).select_related()
    features, targets = extract_leads_tag(learn_leads, include_leads=True)
    model = get_tag_model()
    model.fit(features, targets)
    g = GridSearchCV(model, parameters, verbose=2, n_jobs=1, scoring=score_tag_lead, cv=3)
    g.fit(features, targets)
    return g


def grid_cv_state_model():
    """Perform a grid search cross validation to find best parameters"""
    parameters = {
        'clf__criterion': ("gini", "entropy", "log_loss"),
        'clf__min_samples_split': (2, 3, 5, 8, 10, 12),
        'clf__min_samples_leaf': (1, 2, 5, 8, 10),
        'clf__class_weight': ("balanced", "balanced_subsample"),
        'clf__max_features': ("sqrt", "log2", None),
    }
    learn_leads = Lead.objects.filter(state__in=list(STATES.keys()))
    features, targets = extract_leads_state(learn_leads)
    model = get_state_model()
    g = GridSearchCV(model, parameters, verbose=1, n_jobs=-1, cv=3, scoring="f1_macro")
    g.fit(features, process_target(targets))
    eval_state_model(g.best_estimator_)
    return g


def score_tag_lead(model, X, y):
    """Score function used to cross validated tag model"""
    lead_id_match = re.compile(r"(\d+)\s.*")
    ok = 0.0
    leads = cache.get("ALL_LEADS")
    if leads is None:
        leads = dict([(i.id, i) for i in Lead.objects.all()])
        cache.set("ALL_LEADS", leads, 1800)
    for features, target in zip(X, y):
        try:
            lead_id = lead_id_match.match(features).group(1)
            lead = leads[int(lead_id)]
            predict = model.predict([features])[0]
            if str(predict).lower() in [str(t).lower() for t in lead.tags.all()]:
                ok += 1
        except Exception as e:
            print("Failed to score lead %s: %s" % (lead_id, e))

    return ok / len(X)


############# Entry points for prediction ##########################

def predict_state(model, features):
    result = []
    for scores in model.predict_proba(features):
        proba = {}
        for state, score in zip(model.classes_, scores):
            proba[INV_STATES[state]] = int(round(100 * score))
        result.append(proba)
    return result


def predict_tags(lead):
    model = compute_leads_tags(return_model=True)
    if model is None:
        # cannot compute model (ex. not enough data, no scikit...)
        return []
    features = get_lead_tag_data(lead)
    scores = model.predict_proba([features, ])
    proba = list(zip(model.classes_, scores[0]))
    proba.sort(key=lambda x: x[1])
    best_proba = []
    for i in range(3):
        try:
            tag, score = proba.pop()
            tag = Tag.objects.get(name=str(tag))
            best_proba.append(tag)
        except IndexError:
            break  # No more tag for this lead
        except (Tag.DoesNotExist, Tag.MultipleObjectsReturned):
            # Tag was removed or two tag with same name (bad data before data cleaning)
            pass

    return best_proba


def predict_similar(lead):
    model = compute_lead_similarity(return_model=True)
    leads_ids = cache.get(SIMILARITY_LEADS_IDS_CACHE_KEY)
    scaler = cache.get(SIMILARITY_LEADS_SALES_SCALER_CACHE_KEY)
    similar_leads = []
    if model is None or scaler is None:
        # cannot compute model (ex. not enough data, no scikit...)
        return []
    features, scaler = extract_leads_similarity([lead, ], scaler)
    vect = model.named_steps["vect"]
    neigh = model.named_steps["neigh"]
    indices = neigh.kneighbors(vect.transform(features), return_distance=False)
    if indices.any():
        try:
            similar_leads_ids = [leads_ids[indice] for indice in indices[0]]
            similar_leads = Lead.objects.filter(pk__in=similar_leads_ids).exclude(pk=lead.id).select_related()
        except IndexError:
            print("While searching for lead similarity, some lead disapeared !")
    return similar_leads


############# Entry points for computation ##########################
@shared_task(rate_limit="10/h")
def compute_leads_state(relearn=True, leads_id=None):
    """Learn state from past leads and compute state probal for current leads. This function is intended to be run async
    as it could last few seconds.
    @:param relearn; if true (default) learn again from leads, else, use previous computation if available
    @:param leads_id: estimate those leads. All current leads if None. Parameter is a list of id to ease serialisation"""
    if not HAVE_SCIKIT:
        return

    # only predict proba for in-progress leads
    current_leads = Lead.objects.exclude(state__in=list(STATES.keys()))

    # only work on given leads
    if leads_id:
        current_leads = current_leads.filter(id__in=leads_id)

    if current_leads.count() == 0:
        # nothing to do
        return

    current_features, current_targets = extract_leads_state(current_leads)

    model = cache.get(STATE_MODEL_CACHE_KEY)
    if relearn or model is None:
        learn_leads = Lead.objects.filter(state__in=list(STATES.keys()))
        if learn_leads.count() < 5:
            # Cannot learn anything with so few data
            return
        learn_features, learn_targets = extract_leads_state(learn_leads)
        model = get_state_model()
        model.fit(learn_features, process_target(learn_targets))
        cache.set(STATE_MODEL_CACHE_KEY, model, 3600 * 24)

    for lead, score in zip(current_leads, predict_state(model, current_features)):
        for state, proba in list(score.items()):
            s, created = StateProba.objects.get_or_create(lead=lead, state=state, defaults={"score": 0})
            s.score = proba
            s.save()
            if state == "WON":
                for mission in lead.mission_set.filter(probability_auto=True):
                    mission.probability = proba
                    mission.save(update_tasks=False)  # don't update tasks to avoid useless flood


@shared_task(rate_limit="10/h")
def compute_leads_tags(relearn=False, return_model=False):
    """Learn tags from past leads and cache model
    :param relearn: force to recompute model even if valid model is in cache (default is False)
    :param return_model: return computed model. Default is False because model is not serializable as celery result"""

    if not HAVE_SCIKIT:
        return

    model = cache.get(TAG_MODEL_CACHE_KEY)
    if relearn or model is None:
        # Learn from leads with at least 2 tags
        learn_leads = Lead.objects.annotate(n_tags=Count("tags")).filter(n_tags__gte=2)
        if learn_leads.count() < 5:
            # Cannot learn anything with so few data
            return
        features, targets = extract_leads_tag(learn_leads)
        model = get_tag_model()
        model.fit(features, targets)
        cache.set(TAG_MODEL_CACHE_KEY, zlib.compress(pickle.dumps(model, protocol=5), level=1), 3600 * 24 * 7)
    else:
        model = pickle.loads(zlib.decompress(model))

    if return_model:
        return model


@shared_task(rate_limit="10/h")
def compute_lead_similarity(relearn=False, return_model=False):
    """Compute a model to find similar leads and cache it
    :param relearn: force to recompute model even if valid model is in cache (default is False)
    :param return_model: return computed model. Default is False because model is not serializable as celery result"""

    if not HAVE_SCIKIT:
        return

    model = cache.get(SIMILARITY_MODEL_CACHE_KEY)
    if relearn or model is None:
        leads = Lead.objects.all().select_related("subsidiary")
        if leads.count() < 5:
            # Cannot learn anything with so few data
            return
        scaler = MinMaxScaler()
        learn_features, scaler = extract_leads_similarity(leads, scaler)
        features, scaler = extract_leads_similarity(leads, scaler)
        model = get_similarity_model()
        model.fit(learn_features)
        cache.set(SIMILARITY_MODEL_CACHE_KEY, model, 3600 * 24 * 7)
        cache.set(SIMILARITY_LEADS_IDS_CACHE_KEY, [i.id for i in leads], 3600 * 24 * 7)
        cache.set(SIMILARITY_LEADS_SALES_SCALER_CACHE_KEY, scaler, 3600 * 24 * 7)

    if return_model:
        return model
