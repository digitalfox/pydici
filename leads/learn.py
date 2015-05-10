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
    from sklearn.linear_model import LogisticRegression
except ImportError:
    HAVE_SCIKIT = False

from django.db import transaction
from django.core.cache import cache

from leads.models import Lead, StateProba
from taggit_suggest.models import Tag


STATES= { "WON": 1, "LOST": 2, "SLEEPING": 3, "FORGIVEN": 4}
INV_STATES = dict([(v, k) for k, v in STATES.items()])


def get_lead_data(lead, tags):
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


def extract_leads(leads):
    """Extract leads features and targets"""
    features = []
    targets = []
    tags = Tag.objects.all()
    for lead in leads:
        try:
            feature, target = get_lead_data(lead, tags)
            features.append(feature)
            targets.append(target)
        except Exception, e:
            print "Cannot process lead %s (%s)" % (lead.id, e)
    return (features, targets)


def processTarget(targets):
    return [STATES[i] for i in targets]


def learn(features, targets):
    m = LogisticRegression()
    m.fit(features, targets)
    return m


def predict(model, features):
    result = []
    for scores in model.predict_proba(features):
        proba = {}
        for state, score in zip(model.classes_, scores):
            proba[INV_STATES[state]] = round(100*score,1)
        result.append(proba)
    return result

def test_model():
    """Test model accuracy"""
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
    learn_features, learn_targets = extract_leads(learn_leads)
    test_features, test_targets = extract_leads(test_leads)
    vectorizer = DictVectorizer()
    vectorizer.fit(learn_features+test_features)
    model = learn(vectorizer.transform(learn_features), processTarget(learn_targets))
    score = model.score(vectorizer.transform(test_features), processTarget(test_targets))
    print "score : %s" % score
    return score

@transaction.atomic
def compute_leads_state(relearn=True, leads=None):
    """Learn from past leads and compute stats for current leads
    @:param learn; if true (default) learn again from leads, else, use previous computation if available
    @:param leads: estimate those leads. All current leads if None"""
    MODEL_CACHE_KEY = "PYDICI_LEAD_LEARN_MODEL"
    if not HAVE_SCIKIT:
        return

    current_leads = leads or Lead.objects.exclude(state__in=STATES.keys())
    current_features, current_targets = extract_leads(current_leads)

    model_and_vectorizer = cache.get(MODEL_CACHE_KEY)
    if relearn or model_and_vectorizer is None:
        learn_leads = Lead.objects.filter(state__in=STATES.keys())
        learn_features, learn_targets = extract_leads(learn_leads)
        vectorizer = DictVectorizer()
        vectorizer.fit(learn_features)
        model = learn(vectorizer.transform(learn_features), processTarget(learn_targets))
        cache.set(MODEL_CACHE_KEY, (model, vectorizer), 3600*24)
    else:
        model, vectorizer = model_and_vectorizer

    for lead, score in zip(current_leads, predict(model, vectorizer.transform(current_features))):
        for state, proba in score.items():
            s, created = StateProba.objects.get_or_create(lead=lead, state=state, defaults={"score":0})
            s.score = proba
            s.save()
            if state == "WON":
                for mission in lead.mission_set.filter(probability_auto=True):
                    mission.probability = proba
                    mission.save()



