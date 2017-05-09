import logging
from flask import Flask, render_template
from flask_ask import Ask, statement, question, session
from eventbrite import Eventbrite
import csv

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
    session.attributes['desired_time']= desired_time
    checking_msg = render_template('event check', desired_time=desired_time)
    return question(checking_msg)


@ask.intent ("SatisfactionIntent", convert={'satisfaction_response': str})
def generate_recommendations(address, category_input, subcategory_input, location_radius, event_timing):

    #GET CATEGORY ID FROM CATEGORY NAME
    eventbrite = Eventbrite('7BKHCZRFPHVW5PN262TD')
    address = '181 3rd St, San Francisco, CA 94103'
    category_input = 'Music'
    subcategory_input = 'Pop'
    location_radius = '1mi'
    event_timing = store_desired_time
    categoryquery = eventbrite.get_categories()
    # print(categoryquery)

    category_name = [c['name'] for c in categoryquery['categories']]
    category_ids = [c['id'] for c in categoryquery['categories']]
    categories = zip(category_name, category_ids)

    for x in categories:
        if x[0] == category_input:
            category_id = x[1]

    #GET SUBCATEGORY ID FROM CATEGORY ID
    subcategoryquery = eventbrite.get_subcategories()
    # print(categoryquery)

    subcategory_name = [c['name'] for c in subcategoryquery['subcategories']]
    subcategory_ids = [c['id'] for c in subcategoryquery['subcategories']]
    subcategories = zip(subcategory_name, subcategory_ids)

    for x in subcategories:
        if x[0] == subcategory_input:
            subcategory_id = x[1]

    #GET LIST OF EVENTS
    eventbrite = Eventbrite('tag')
    eventquery = eventbrite.event_search(**{'location.address': address}, **{'categories': category_id},
                                         **{'subcategories': subcategory_id}, **{'location.within': location_radius},
                                         **{'start_date.keyword': event_timing})
    # print(eventquery)

    eventnames = [t['text'] for t in (e['name'] for e in eventquery['events'])]
    # print(eventnames)
    event1 = eventnames[0]
    print(event1)

    recommendation_msg = render_template('recommendation', event1=event1)
    return question(recommendation_msg)

    eventdescr = [t['text'] for t in (e['description'] for e in eventquery['events'])]
    # print(eventdescr)

    #COLLECT ADDITIONAL INFO FOR FILES
    eventdescr2 = []
    for i in eventdescr:
        eventdescr2.append((((i).replace("\n", " ")).replace("\r", " "))[0:30])
    # print(eventdescr2)

    eventlogo = [u['url'] for u in (o['original'] for o in (e['logo'] for e in eventquery['events']))]
    # print(eventlogo)

    eventkeys = []
    for i in eventnames:
        eventkeys.append(('event-' + i).replace(" ", "-"))
    # print(eventkeys)

    eventempty = []
    for i in range(1, event_count):
        eventempty.append("")
    # print(eventempty)

    eventlist = zip(eventkeys, eventnames, eventdescr2, eventempty, eventlogo)

    ###################################
    ### CREATE EVENT TERMS ###

    eventterms = []
    for i in eventnames:
        eventterms.append((((category_input + '__' + subcategory_input).replace(" ", "_")).replace("/", "and")).lower())

    termfile = zip(eventkeys, eventterms)

    ### PUT EVENT DETAILS INTO PRODUCTS FILE ###

    with open('/Users/alison.e.oneill/products.tsv', 'a') as f:
        w = csv.writer(f, delimiter='\t')
        for i in eventlist:
            w.writerow(i)

    with open('/Users/alison.e.oneill/terms.tsv', 'a') as f:
        w = csv.writer(f, delimiter='\t')
        for i in termfile:
            w.writerow(i)

if __name__ == '__main__':
    app.run(debug=True)