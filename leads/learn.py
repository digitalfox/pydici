# coding: utf-8

"""
Module that handle predictive state of a lead
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import datetime, date
import re
import zlib
import cPickle

HAVE_SCIKIT = True
try:
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.linear_model import SGDClassifier
    from sklearn.cross_validation import cross_val_score, train_test_split
    from sklearn.grid_search import GridSearchCV
    from sklearn.metrics import confusion_matrix, classification_report, f1_score
    import numpy as np
except ImportError:
    HAVE_SCIKIT = False

from django.db.models import Count
from django.core.cache import cache

from leads.models import Lead, StateProba
from taggit.models import Tag


STATES= { "WON": 1, "LOST": 2, "FORGIVEN": 3}
INV_STATES = dict([(v, k) for k, v in STATES.items()])

TAG_MODEL_CACHE_KEY = "PYDICI_LEAD_LEARN_TAGS_MODEL"
STATE_MODEL_CACHE_KEY = "PYDICI_LEAD_LEARN_STATE_MODEL"

def get_lead_state_data(lead, tags):
    """Get features and target of given lead. Raise Exception if lead data cannot be extracted (ie. incomplete)"""
    feature = {}
    feature["responsible"] = unicode(lead.responsible)
    feature["client_orga"] = unicode(lead.client.organisation)
    feature["client_contact"] = unicode(lead.client.contact)
    if lead.state in STATES.keys() and lead.start_date:
        feature["lifetime"] = (lead.start_date - lead.creation_date.date()).days
    else:
        feature["lifetime"] = (date.today() - lead.creation_date.date()).days
    feature["sales"] = float(lead.sales or 0)
    feature["broker"] = unicode(lead.business_broker)
    feature["paying_authority"] = unicode(lead.paying_authority)
    feature["lead_client_rank"] = list(lead.client.lead_set.all().order_by("creation_date")).index(lead)
    lead_tags = lead.tags.all()
    for tag in tags:
        if tag in lead_tags:
            feature["tag_%s" % tag.slug] = "yes"
        else:
            feature["tag_%s" % tag.slug] = "no"
    return feature, lead.state


def extract_leads_state(leads):
    """Extract leads features and targets for state learning"""
    features = []
    targets = []
    tags = Tag.objects.all()
    for lead in leads:
        try:
            feature, target = get_lead_state_data(lead, tags)
            features.append(feature)
            targets.append(target)
        except Exception, e:
            print "Cannot process lead %s (%s)" % (lead.id, e)
    return (features, targets)


def processTarget(targets):
    return [STATES[i] for i in targets]


def get_state_model():
    model = Pipeline([("vect", DictVectorizer()), ("clf", LogisticRegression(penalty="l2",
                                                                             solver="liblinear",
                                                                             C=1,
                                                                             class_weight="balanced"))])
    return model


def predict_state(model, features):
    result = []
    for scores in model.predict_proba(features):
        proba = {}
        for state, score in zip(model.classes_, scores):
            proba[INV_STATES[state]] = int(round(100*score))
        result.append(proba)
    return result


def get_lead_tag_data(lead):
    """Extract lead data needed to predict tag"""
    return " ".join([unicode(lead.client.organisation), unicode(lead.responsible),
                                      unicode(lead.subsidiary), unicode(lead.name),
                                      unicode(lead.staffing_list()), unicode(lead.description)])


def extract_leads_tag(leads, include_leads=False):
    """Extract leads features and targets for tag learning
    @:param include_leads : add leads id at the begining of features for model testing purpose"""
    features = []
    targets = []
    used_leads = []
    for lead in leads:
        for tag in lead.tags.all():
            used_leads.append(lead)
            targets.append(unicode(tag))
            if include_leads:
                features.append(u"%s %s" % (lead.id, get_lead_tag_data(lead)))
            else:
                features.append(get_lead_tag_data(lead))
    return (features, targets)


def learn_tag(features, targets):
        model = Pipeline([("vect", CountVectorizer()), ("trf", TfidfTransformer(sublinear_tf=True)),
                           ("clf", SGDClassifier(loss="log", penalty="l1"))])
        model.fit(features, targets)
        return model


def predict_tags(lead):
    model = compute_leads_tags()
    if model is None:
        # cannot compute model (ex. not enough data, no scikit...)
        return []
    features = get_lead_tag_data(lead)
    scores = model.predict_proba([features,])
    proba = []
    for tag, score in zip(model.classes_, scores[0]):
        try:
            proba.append([Tag.objects.get(name=unicode(tag)), round(100*score,1)])
        except (Tag.DoesNotExist,Tag.MultipleObjectsReturned):
            # Tag was removed or two tag with same name (bad data before data cleaning)
            pass
    proba.sort(key=lambda x: x[1])
    best_proba = []
    for i in range(3):
        try:
            best_proba.append(proba.pop())
        except IndexError:
            break
    return [i[0] for i in best_proba]


def test_state_model():
    """Test state model accuracy"""
    leads = Lead.objects.filter(state__in=STATES.keys())
    features, targets = extract_leads_state(leads)
    model = get_state_model()
    model.fit(features, processTarget(targets))
    scores = cross_val_score(model, features, processTarget(targets))
    print("Score : %0.2f (+/- %0.2f)" % (scores.mean(), scores.std() * 2))
    return scores.mean()


def eval_state_model(model=None):
    """Display confusion matrix and classif report state model"""
    target_names = STATES.items()
    target_names.sort(key=lambda x: x[1])
    target_names = [i[0] for i in target_names]
    leads = Lead.objects.filter(state__in=STATES.keys())
    features, targets = extract_leads_state(leads)
    X_train, X_test, y_train, y_test = train_test_split(features, processTarget(targets), test_size=0.2, random_state=0)
    if model is None:
        model = get_state_model()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    print confusion_matrix(y_test, y_pred)
    print classification_report(y_test, y_pred, target_names=target_names)
    feature_names = model.named_steps["vect"].get_feature_names()
    for i, class_label in enumerate(target_names):
        try:
            coef = model.named_steps["clf"].coef_
            top = np.argsort(coef[i])[-10:][::-1]
            print("%s: \n- %s" % (class_label,
                  "\n- ".join("%s (%s)" % (feature_names[j], round(coef[i][j],2))  for j in top)))
        except IndexError:
            # Model has no coef for this class
            pass
    return model


def test_tag_model():
    """Test tag model accuracy"""
    leads = Lead.objects.annotate(n_tags=Count("tags")).filter(n_tags__gte=2)
    test_features, test_targets = extract_leads_tag(leads, include_leads=True)
    model = learn_tag(test_features, test_targets)
    scores = cross_val_score(model, test_features, test_targets, scoring=score_tag_lead)
    m = cPickle.dumps(model)
    print "size %s - compressed %s" % (len(m)/(1024*1024), len(zlib.compress(m))/(1024*1024))
    print("Score : %0.2f (+/- %0.2f)" % (scores.mean(), scores.std() * 2))
    return scores.mean()


def gridCV_tag_model():
    """Perform a grid search cross validation to find best parameters"""
    parameters=  {'clf__alpha': (0.1, 0.01, 0.001, 0.0001, 1e-05),
     'clf__loss': ('log', 'modified_huber', 'squared_hinge'),
     'clf__penalty': ('none', 'l2', 'l1', 'elasticnet'),
     'trf__norm': ('l1', 'l2'),
     'trf__sublinear_tf': (True, False),
     'trf__use_idf': (True, False)}

    learn_leads = Lead.objects.annotate(n_tags=Count("tags")).filter(n_tags__gte=2)
    features, targets = extract_leads_tag(learn_leads, include_leads=True)
    model = learn_tag(features, targets)
    g=GridSearchCV(model, parameters, verbose=2, n_jobs=4, scoring=score_tag_lead)
    g.fit(features, targets)
    return g


def gridCV_state_model():
    """Perform a grid search cross validation to find best parameters"""
    parameters= {'clf__penalty': ('l2', 'l1'),
                 'clf__C': (0.001, 0.003, 0.004, 0.005, 0.01, 0.1, 1),
                 'clf__class_weight' : (None, "auto")
                }
    learn_leads = Lead.objects.filter(state__in=STATES.keys())
    features, targets = extract_leads_state(learn_leads)
    model = get_state_model()
    g=GridSearchCV(model, parameters, verbose=1, n_jobs=6)
    g.fit(features, processTarget(targets))
    eval_state_model(g.best_estimator_)
    return g


def score_tag_lead(model, X, y):
    """Score function used to cross validated tag model"""
    lead_id_match = re.compile("(\d+)\s.*")
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
            if unicode(predict).lower() in [unicode(t).lower() for t in lead.tags.all()]:
                ok +=1
        except Exception, e:
            print "Failed to score lead %s: %s" % (lead_id, e)

    return ok / len(X)


def compute_leads_state(relearn=True, leads_id=None):
    """Learn state from past leads and compute state probal for current leads. This function is intended to be run async
    as it could last few seconds.
    @:param learn; if true (default) learn again from leads, else, use previous computation if available
    @:param leads_id: estimate those leads. All current leads if None. Parameter is a list of id to avoid passing ORM objects across threads"""
    if not HAVE_SCIKIT:
        return
    if leads_id:
        current_leads = Lead.objects.filter(id__in=leads_id)
    else:
        current_leads = Lead.objects.exclude(state__in=STATES.keys())

    current_features, current_targets = extract_leads_state(current_leads)

    model = cache.get(STATE_MODEL_CACHE_KEY)
    if relearn or model is None:
        learn_leads = Lead.objects.filter(state__in=STATES.keys())
        if learn_leads.count() < 5:
            # Cannot learn anything with so few data
            return
        learn_features, learn_targets = extract_leads_state(learn_leads)
        model = get_state_model()
        model.fit(learn_features, processTarget(learn_targets))
        cache.set(STATE_MODEL_CACHE_KEY, model, 3600*24)

    for lead, score in zip(current_leads, predict_state(model, current_features)):
        for state, proba in score.items():
            s, created = StateProba.objects.get_or_create(lead=lead, state=state, defaults={"score":0})
            s.score = proba
            s.save()
            if state == "WON":
                for mission in lead.mission_set.filter(probability_auto=True):
                    mission.probability = proba
                    mission.save()


def compute_leads_tags():
    """Learn tags from past leads and cache model"""

    if not HAVE_SCIKIT:
        return

    model = cache.get(TAG_MODEL_CACHE_KEY)
    if model is None:
        # Learn from leads with at least 2 tags
        learn_leads = Lead.objects.annotate(n_tags=Count("tags")).filter(n_tags__gte=2)
        if learn_leads.count() < 5:
            # Cannot learn anything with so few data
            return
        features, targets = extract_leads_tag(learn_leads)
        model = learn_tag(features, targets)
        cache.set(TAG_MODEL_CACHE_KEY, zlib.compress(cPickle.dumps(model)), 3600*24)
    else:
        model = cPickle.loads(zlib.decompress(model))

    return model

