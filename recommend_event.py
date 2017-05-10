import csv
import io
import logging

from eventbrite import Eventbrite
from flask import Flask, render_template
from flask_ask import Ask, question, session, statement


app = Flask(__name__)
ask = Ask(app, "/")
logging.getLogger("flask_ask").setLevel(logging.DEBUG)


@ask.launch
def new_interaction():
    welcome_msg = render_template('welcome')
    return question(welcome_msg)


@ask.intent("NameIntent", convert={'guest_name': str})
def store_name(guest_name):
    session.attributes['guest_name'] = guest_name
    offer_msg = render_template('offer help', guest_name=guest_name)
    return question(offer_msg)


@ask.intent("EventIntent")
def new_recommendation():
    start_msg = render_template('start')
    return question(start_msg)


@ask.intent("DesiredTimeIntent", convert={'desired_time': str})
def store_desired_time(desired_time):
    session.attributes['desired_time'] = desired_time
    checking_msg = render_template('event check', desired_time=desired_time)
    return question(checking_msg)


@ask.intent("SatisfactionIntent", convert={'satisfaction_response': str})
def generate_recommendations(satisfaction_response):
    event = get_recommendation(session.attributes['desired_time'])
    recommendation_msg = render_template('recommendation', event=event)
    return statement(recommendation_msg)


def get_recommendation(desired_time):
    """Get a recommendation from EventBrite."""
    eventbrite = Eventbrite('7BKHCZRFPHVW5PN262TD')

    # GET CATEGORY ID FROM CATEGORY NAME
    address = '181 3rd St, San Francisco, CA 94103'
    category_input = 'Music'
    subcategory_input = 'EDM / Electronic'
    location_radius = '1mi'
    event_timing = desired_time
    categoryquery = eventbrite.get_categories()

    category_name = [c['name'] for c in categoryquery['categories']]
    category_ids = [c['id'] for c in categoryquery['categories']]
    categories = zip(category_name, category_ids)

    category_id = None
    for x in categories:
        if x[0] == category_input:
            category_id = x[1]

    # GET SUBCATEGORY ID FROM CATEGORY ID
    subcategoryquery = eventbrite.get_subcategories()

    subcategory_name = [c['name'] for c in subcategoryquery['subcategories']]
    subcategory_ids = [c['id'] for c in subcategoryquery['subcategories']]
    subcategories = zip(subcategory_name, subcategory_ids)

    subcategory_id = None
    for x in subcategories:
        if x[0] == subcategory_input:
            subcategory_id = x[1]

    # GET LIST OF EVENTS
    eventquery = eventbrite.event_search(**{'location.address': address,
                                            'categories': category_id,
                                            'subcategories': subcategory_id,
                                            'location.within': location_radius,
                                            'start_date.keyword': event_timing})

    eventnames = [e['name']['text'] for e in eventquery['events']]

    eventdescr = [e['description']['text'] for e in eventquery['events']]

    # COLLECT ADDITIONAL INFO FOR FILES
    eventdescr2 = []
    for i in eventdescr:
        eventdescr2.append(((i.replace("\n", " ")).replace("\r", " "))[0:30])

    eventlogo = []
    for e in eventquery['events']:
        eventlogo.append(e['logo']['original']['url'] if e['logo'] else '')

    eventkeys = []
    for i in eventnames:
        eventkeys.append(('event-' + i).replace(" ", "-"))

    eventlist = zip(eventkeys, eventnames, eventdescr2, ['']*len(eventkeys), eventlogo)

    ###################################
    # CREATE EVENT TERMS ###

    eventterms = []
    for i in eventnames:
        eventterms.append((((category_input + '__' + subcategory_input).replace(" ", "_")).replace("/", "and")).lower())

    termfile = zip(eventkeys, eventterms)

    # PUT EVENT DETAILS INTO PRODUCTS FILE ###

    with io.open('products.tsv', 'a', encoding='utf-8') as f:
        w = csv.writer(f, delimiter='\t')
        for i in eventlist:
            w.writerow(i)

    with io.open('terms.tsv', 'a', encoding='utf-8') as f:
        w = csv.writer(f, delimiter='\t')
        for i in termfile:
            w.writerow(i)

    return eventnames[0]


if __name__ == '__main__':
    app.run(debug=True)
