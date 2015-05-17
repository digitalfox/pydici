# coding: utf-8

"""
Module that handle predictive state of a lead
@author: Sébastien Renard (sebastien.renard@digitalfox.org)
@license: AGPL v3 or newer (http://www.gnu.org/licenses/agpl-3.0.html)
"""

from datetime import datetime, date
from random import sample

HAVE_SCIKIT = True
try:
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.linear_model import SGDClassifier
    from sklearn.preprocessing import MultiLabelBinarizer
    from sklearn.multiclass import LabelBinarizer
except ImportError:
    HAVE_SCIKIT = False

from django.db import transaction
from django.db.models import Count
from django.core.cache import cache

from leads.models import Lead, StateProba
from taggit_suggest.models import Tag


STATES= { "WON": 1, "LOST": 2, "SLEEPING": 3, "FORGIVEN": 4}
INV_STATES = dict([(v, k) for k, v in STATES.items()])


def get_lead_state_data(lead, tags):
    """Get features and target of given lead. Raise Exception if lead data cannot be extracted (ie. incomplete)"""
    feature = {}
    feature["responsible"] = unicode(lead.responsible)
    feature["subsidiary"] = unicode(lead.subsidiary)
    feature["client_orga"] = unicode(lead.client.organisation)
    feature["client_contact"] = unicode(lead.client.contact)
    if lead.state in STATES.keys() and lead.start_date:
        feature["lifetime"] = (lead.start_date - lead.creation_date.date()).days
    else:
        feature["lifetime"] = (date.today() - lead.creation_date.date()).days
    feature["sales"] = float(lead.sales or 0)
    feature["broker"] = unicode(lead.business_broker)
    feature["paying_authority"] = unicode(lead.paying_authority)
    lead_tags = lead.tags.all()
    for tag in tags:
        if tag in lead_tags:
            feature["tag_%s" % tag.id] = "yes"
        else:
            feature["tag_%s" % tag.id] = "no"
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


def learn_state(features, targets):
    m = LogisticRegression()
    m.fit(features, targets)
    return m


def predict_state(model, features):
    result = []
    for scores in model.predict_proba(features):
        proba = {}
        for state, score in zip(model.classes_, scores):
            proba[INV_STATES[state]] = round(100*score,1)
        result.append(proba)
    return result


def extract_leads_tag(leads, include_leads=False):
    """Extract leads features and targets for state learning
    @:param include_leads : add leads return output for model testing purpose"""
    features = []
    targets = []
    used_leads = []
    for lead in leads:
        for tag in lead.tags.all():
            used_leads.append(lead)
            targets.append(unicode(tag))
            features.append(unicode(lead.client) + " " + lead.description)
    if include_leads:
        return (used_leads, features, targets)
    else:
        return (features, targets)


def learn_tag(features, targets):
        model = Pipeline([("vect", CountVectorizer()), ("trf", TfidfTransformer()),
                      ("clf", SGDClassifier(loss="log"))])
        model.fit(features, targets)
        return model


def predict_tags(model, features):
    result = []
    for scores in model.predict_proba(features):
        proba = []
        for tag, score in zip(model.classes_, scores):
            proba.append([tag ,round(100*score,1)])
        proba.sort(key=lambda x: x[1])
        best_proba = []
        for i in range(3):
            try:
                best_proba.append(proba.pop())
            except IndexError:
                break
        result.append(best_proba)
    return result


def test_state_model():
    """Test state model accuracy"""
    leads = Lead.objects.filter(state__in=STATES.keys())
    all_id = list(sum(leads.values_list("id"), ()))
    if len(all_id)<2:
        print "Too few samples"
    test_id = sample(all_id, int(len(all_id)/20) or 1)
    learn_id = all_id
    for i in test_id:
        learn_id.remove(i)
    test_leads = leads.filter(id__in=test_id)
    learn_leads = leads.filter(id__in=learn_id)
    learn_features, learn_targets = extract_leads_state(learn_leads)
    test_features, test_targets = extract_leads_state(test_leads)
    vectorizer = DictVectorizer()
    vectorizer.fit(learn_features+test_features)
    model = learn_state(vectorizer.transform(learn_features), processTarget(learn_targets))
    score = model.score(vectorizer.transform(test_features), processTarget(test_targets))
    print "score : %s" % score
    return score

def test_tag_model():
    """Test tag model accuracy"""
    leads = Lead.objects.annotate(n_tags=Count("tags")).filter(n_tags__gte=2)
    all_id = list(sum(leads.values_list("id"), ()))
    if len(all_id)<2:
        print "Too few samples"
    test_id = sample(all_id, int(len(all_id)/20) or 1)
    learn_id = all_id
    for i in test_id:
        learn_id.remove(i)
    test_leads = leads.filter(id__in=test_id)
    learn_leads = leads.filter(id__in=learn_id)
    learn_features, learn_targets = extract_leads_tag(learn_leads)
    used_test_leads, test_features, test_targets = extract_leads_tag(test_leads, include_leads=True)
    model = learn_tag(learn_features, learn_targets)

    ok = 0.0
    for lead, predict in zip(used_test_leads, model.predict(test_features)):
        if unicode(predict).lower() in [unicode(t).lower() for t in lead.tags.all()]:
            ok += 1
    score = 100 * ok / len(used_test_leads)
    print "Per tag score : %s" % score
    return score


@transaction.commit_on_success
def compute_leads_state(relearn=True, leads=None):
    """Learn state from past leads and compute state probal for current leads
    @:param learn; if true (default) learn again from leads, else, use previous computation if available
    @:param leads: estimate those leads. All current leads if None"""
    MODEL_CACHE_KEY = "PYDICI_LEAD_LEARN_STATE_MODEL"
    if not HAVE_SCIKIT:
        return

    current_leads = leads or Lead.objects.exclude(state__in=STATES.keys())
    current_features, current_targets = extract_leads_state(current_leads)

    model_and_vectorizer = cache.get(MODEL_CACHE_KEY)
    if relearn or model_and_vectorizer is None:
        learn_leads = Lead.objects.filter(state__in=STATES.keys())
        learn_features, learn_targets = extract_leads_state(learn_leads)
        vectorizer = DictVectorizer()
        vectorizer.fit(learn_features)
        model = learn_state(vectorizer.transform(learn_features), processTarget(learn_targets))
        cache.set(MODEL_CACHE_KEY, (model, vectorizer), 3600*24)
    else:
        model, vectorizer = model_and_vectorizer

    for lead, score in zip(current_leads, predict_state(model, vectorizer.transform(current_features))):
        for state, proba in score.items():
            s, created = StateProba.objects.get_or_create(lead=lead, state=state, defaults={"score":0})
            s.score = proba
            s.save()
            if state == "WON":
                for mission in lead.mission_set.filter(probability_auto=True):
                    mission.probability = proba
                    mission.save()


def compute_leads_tags(relearn=True, leads=None):
    """Learn tags from past leads and compute tags for current leads
    @:param learn; if true (default) learn again from leads, else, use previous computation if available
    @:param leads: estimate those leads. All current leads if None"""
    MODEL_CACHE_KEY = "PYDICI_LEAD_LEARN_TAGS_MODEL"
    if not HAVE_SCIKIT:
        return

    model = cache.get(MODEL_CACHE_KEY)
    if model is None:
        pass
    # Get leads with less than 3 tags
    current_leads = leads or Lead.objects.annotate(n_tags=Count("tags")).filter(n_tags__lt=3)
    # Learn from leads with at least 2 tags
    learn_leads = leads or Lead.objects.annotate(n_tags=Count("tags")).filter(n_tags__gte=2)

    features = targets = extract_leads_tag(learn_leads)
    model = learn_tag(features, targets)



