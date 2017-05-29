import csv
import io
import logging
import googlemaps

from eventbrite import Eventbrite
from flask import Flask, render_template
from flask_ask import Ask, request, session, question, statement, context, audio, current_stream


app = Flask(__name__)
ask = Ask(app, "/")
logging.getLogger("flask_ask").setLevel(logging.DEBUG)

def get_key(api_source):
    with io.open('api_keys.csv', 'r') as f:
        r = csv.DictReader(f, fieldnames=("api_source","api_key"))
        for row in r:
            if row['api_source'] == api_source:
                return row['api_key']


@ask.launch
def new_interaction():
    welcome_msg = render_template('welcome')
    return question(welcome_msg)


@ask.intent("RoomIntent", convert={'room_number': int})
def store_room_number(room_number):
    session.attributes['room_number'] = room_number
    room_number = str(room_number)
    with io.open('guests.csv', 'r') as f:
        r = csv.DictReader(f, fieldnames=("room_number", "first_name", "last_name", "hotel","phone_number", "music_cat", "music_cat_id"))
        for row in r:
            file_room_number = row['room_number']
            if file_room_number == room_number:
                guest_name = row['first_name']
                session.attributes['guest_name'] = guest_name
                session.attributes['hotel'] = row['hotel']
                session.attributes['phone_number'] = row['phone_number']
                session.attributes['music_cat_id'] = row['music_cat_id']
    offer_msg = render_template('offer help', guest_name=guest_name)
    return question(offer_msg)


@ask.intent("EventIntent")
def new_recommendation():
    start_msg = render_template('start')
    return question(start_msg)


@ask.intent("DesiredTimeIntent", convert={'desired_time': str})
def store_desired_time(desired_time):
    desired_time_var = desired_time.replace(" ","_")
    print(desired_time)
    session.attributes['desired_time'] = desired_time_var
    checking_msg = render_template('event check', desired_time=desired_time)
    return question(checking_msg)


@ask.intent("SatisfactionIntent", convert={'satisfaction_response': str})
def generate_recommendations(satisfaction_response):
    event = get_recommendation(session.attributes['desired_time'])
    recommendation_msg = render_template('recommendation', event=event)
    return statement(recommendation_msg)


def get_recommendation(desired_time):
    """Get a recommendation from EventBrite."""
    eventbrite_api_key = get_key('eventbrite')
    eventbrite = Eventbrite(eventbrite_api_key)

    # GET ADDRESS FROM HOTEL NAME (GOOGLEMAPS)
    google_api_key = get_key('google')
    gmaps = googlemaps.Client(key=google_api_key)
    places_result = gmaps.places(query=session.attributes['hotel'])
    hotel_address = [e['formatted_address'] for e in places_result['results']]

    # GET CATEGORY ID FROM CATEGORY NAME
    address = hotel_address
    category_input = 'Music'
    subcategory_input = session.attributes['music_cat_id']
    location_radius = '10mi'
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
    event1 = eventnames[0]

    eventdescr = [e['description']['text'] for e in eventquery['events']]
    descr1 = eventdescr[0]

    # COLLECT ADDITIONAL INFO FOR FILES
    #eventdescr2 = []
    #for i in eventdescr:
        #if i is None:
            #eventdescr2.append("")
        #eventdescr2.append(((i.replace("\n", " ")).replace("\r", " "))[0:30])

    eventlogo = []
    for e in eventquery['events']:
        eventlogo.append(e['logo']['original']['url'] if e['logo'] else '')
    logo1 = eventlogo[0]

    eventkeys = []
    for i in eventnames:
        eventkeys.append(('event-' + i).replace(" ", "-"))

    eventlist = zip(eventkeys, eventnames, eventnames, ['']*len(eventkeys), eventlogo)

    eventstart = [l['local'] for l in (e['start'] for e in eventquery['events'])]
    start1 = eventstart[0]

    eventend = [l['local'] for l in (e['end'] for e in eventquery['events'])]
    end1 = eventend[0]

    eventvenue = [v['venue_id'] for v in eventquery['events']]
    venue1 = eventvenue[0]
    venuequery = eventbrite.get('/venues/{0}'.format(venue1))
    a = []
    venue_list = venuequery['address']['localized_multi_line_address_display']
    venue_string = " ".join(str(x) for x in venue_list)

    eventurl = [u['url'] for u in eventquery['events']]
    url1 = eventurl[0]

     # CREATE EVENT TERMS

    eventterms = []
    for i in eventnames:
        eventterms.append((((category_input + '__' + subcategory_input).replace(" ", "_")).replace("/", "and")).lower())

    termfile = zip(eventkeys, eventterms)

    # PUT EVENT DETAILS INTO PRODUCTS FILE

    with io.open('products.tsv', 'a', encoding='utf-8') as f:
        w = csv.writer(f, delimiter='\t')
        for i in eventlist:
            w.writerow(i)

    with io.open('terms.tsv', 'a', encoding='utf-8') as f:
        w = csv.writer(f, delimiter='\t')
        for i in termfile:
            w.writerow(i)

    # TEXT EVENT DETAILS
    from twilio.rest import Client

    account_sid = get_key('twilio_sid')
    auth_token = get_key('twilio_token')

    client = Client(account_sid, auth_token)

    client.messages.create(
        to=session.attributes['phone_number'],
        from_=get_key('twilio_phone'),
        body="Your IHG Concierge has sent you an event you may enjoy: " + '\n' + event1 + '\n' + descr1[:800] + '\n' + "Start Time: " + start1 + '\n' + "End Time: " + end1 + '\n' + "Venue: " + venue_string + '\n' + url1,
        media_url=logo1)

    return eventnames[0]

@ask.intent('AMAZON.StopIntent')
def stop():
    return audio('stopping').clear_queue(stop=True)

if __name__ == '__main__':
    app.run(debug=True)