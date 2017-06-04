import csv
import io
import logging
import os

import googlemaps
import spotipy
import datetime
from eventbrite import Eventbrite
from flask import Flask, render_template
from flask_ask import Ask, request, session, question, statement, context, audio, current_stream
from tempfile import NamedTemporaryFile
import shutil
from spotipy.oauth2 import SpotifyClientCredentials


app = Flask(__name__)
ask = Ask(app, "/")
logging.getLogger("flask_ask").setLevel(logging.DEBUG)
reprompt_txt = "I didn't get that, "

def get_key(api_source):
    with io.open('api_keys.csv', 'r') as f:
        r = csv.DictReader(f, fieldnames=("api_source","api_key"))
        for row in r:
            if row['api_source'] == api_source:
                return row['api_key']


@ask.launch
def new_interaction():
    welcome_msg = render_template('welcome')
    reprompt_welcome_msg = render_template('reprompt welcome')
    return question(welcome_msg) \
        .reprompt(reprompt_txt + reprompt_welcome_msg)


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
                session.attributes['music_cat'] = row['music_cat']
                session.attributes['music_cat_id'] = row['music_cat_id']
    offer_msg = render_template('offer help', guest_name=guest_name)
    reprompt_offer_msg = render_template('reprompt offer help')
    return question(offer_msg) \
        .reprompt(reprompt_txt + reprompt_offer_msg)


@ask.intent("MusicIntent")
def new_music_request():
    music_offer = render_template('music offer')
    reprompt_music_offer = render_template('music offer')
    return question(music_offer) \
        .reprompt(reprompt_txt + reprompt_music_offer)


@ask.intent("PlayAudio", convert={'guest_artist': str})
def play_audio(guest_artist):
    session.attributes['guest_artist'] = guest_artist
    artist_request = guest_artist
    stream_url = get_url(artist_request)
    if not stream_url:
        no_result = render_template('no result', guest_artist=guest_artist)
        return question(no_result)
    speech = "Here's one of my favorites"
    return audio(speech).play(stream_url, offset=0)


@ask.intent("EventIntent")
def new_recommendation():
    start_msg = render_template('start')
    reprompt_start_msg = render_template('reprompt start')
    return question(start_msg) \
        .reprompt(reprompt_txt + reprompt_start_msg)


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
    if not event:
        no_event = render_template('no event', desired_time=session.attributes['desired_time'])
        return question(no_event)
    recommendation_msg = render_template('recommendation', event=event)
    return statement(recommendation_msg)


def get_recommendation(desired_time):
    #GET EVENT RECOMMENDATION FROM EVENTBRITE

    # GET EVENTBRITE API KEY
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
    #subcategoryquery = eventbrite.get_subcategories()

    #subcategory_name = [c['name'] for c in subcategoryquery['subcategories']]
    #subcategory_ids = [c['id'] for c in subcategoryquery['subcategories']]
    #subcategories = zip(subcategory_name, subcategory_ids)

    subcategory_id = subcategory_input
    #for x in subcategories:
        #if x[0] == subcategory_input:
            #subcategory_id = x[1]

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
        eventterms.append((((category_input + '__' + session.attributes['music_cat']).replace(" ", "_")).replace("/", "and")).lower())

    termfile = zip(eventkeys, eventterms)

    # PUT EVENT DETAILS INTO PRODUCTS FILE AND TERMS FILE
    with io.open('products.tsv', 'a', encoding='utf-8') as f:
        w = csv.writer(f, delimiter='\t')
        if f.tell() !=3:
            w.writerow("")
        for i in eventlist:
            w.writerow(i)
        f.seek(f.tell() - len(os.linesep))
        f.truncate()

    with io.open('terms.tsv', 'a', encoding='utf-8') as f:
        w = csv.writer(f, delimiter='\t')
        if f.tell() !=3:
            w.writerow("")
        for i in termfile:
            w.writerow(i)
        f.seek(f.tell() - len(os.linesep))
        f.truncate()

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

def get_url(artist_request):

    # USE SPOTIFY CLIENT CREDENTIALS FROM API KEYS FILE
    spotify_client_id = get_key('spotify_client_id')
    spotify_client_secret = get_key('spotify_client_secret')
    client_credentials_manager = SpotifyClientCredentials(client_id=spotify_client_id,
                                                          client_secret=spotify_client_secret)
    spot = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

    # GET ARTIST ID FROM SPOTIFY
    artistquery = spot.search(q=artist_request, type='artist')

    artist_id = [e['id'] for e in artistquery['artists']['items']]
    if not artist_id:
        return ""
    artist_id_str = ''.join(artist_id[0])

    # GET ARTIST GENRES FROM SPOTIFY AND MAP TO EVENTBRITE GENRES
    artist_genres = [g for g in (e['genres'] for e in artistquery['artists']['items'])]
    artist_genres = artist_genres[0]

    primary_genre = artist_genres[0].lower()

    with io.open('category_map.csv', 'r') as f:
        r = csv.DictReader(f, fieldnames=("Spotify", "Eventbrite", "Subcategory_ID"))
        for row in r:
            if row['Spotify'].lower() == primary_genre:
                session.attributes['eventbrite_cat'] = row['Eventbrite'].replace(" ", "_").lower()
                session.attributes['eventbrite_sub'] = row['Subcategory_ID']
                found_cat_map = True
                break

        # WRITE ERROR LOG FOR MISSING SPOTIFY CATEGORIES IN CATEGORY_MAP.CSV
        try: found_cat_map
        except NameError:
            session.attributes['eventbrite_cat'] = primary_genre
            session.attributes['eventbrite_sub'] = 'check genre'
            session.attributes['category_map_error'] = ["Check category map: " + primary_genre,]
            with open('errors.txt', 'a') as f:
                w = csv.writer(f)
                w.writerow(session.attributes['category_map_error'])

    # UPDATE TERMS FILE WITH ARTIST GENRES
    file_genres = []
    for x in artist_genres:
        file_genres.append(('music__' + x).replace(" ", "_").lower())
    file_genres.append(('music__' + session.attributes['eventbrite_cat']))

    artistset = []
    for i in file_genres:
        artistset.append(('music-' + artist_request).replace(" ", "-").replace("/", "and").lower())

    artisttags = zip(artistset, file_genres)

    with open('terms.tsv', 'a') as f:
        w = csv.writer(f, delimiter='\t')
        if f.tell() !=3:
            w.writerow("")
        for i in artisttags:
            w.writerow(i)
        f.seek(f.tell() - len(os.linesep))
        f.truncate()

    # UPDATE TRANSACTIONS FILE WITH MUSIC INTERACTION
    transactions = []
    transactions.insert(0, "")
    transactions.insert(1, session.attributes['guest_name'].lower())
    transactions.insert(2, ('music-' + artist_request).replace(" ", "-").lower())
    transactions.insert(3, '1')
    transactions = [transactions, ]

    with open('transactions.tsv', 'a') as f:
        w = csv.writer(f, delimiter='\t')
        if f.tell() !=3:
            w.writerow("")
        for i in transactions:
            w.writerow(i)
        f.seek(f.tell() - len(os.linesep))
        f.truncate()



    # UPDATE GUESTS.CSV FILE WITH NEW PREFERRED CATEGORY
    filename = 'guests.csv'
    with NamedTemporaryFile('w', delete=False, encoding='UTF-8') as tempfile:
        with open(filename) as f:
            r = csv.DictReader(f, fieldnames=(
            "room_number", "first_name", "last_name", "hotel", "phone_number", "music_cat", "music_cat_id"))
            w = csv.DictWriter(tempfile, fieldnames=(
            "room_number", "first_name", "last_name", "hotel", "phone_number", "music_cat", "music_cat_id"))
            for row in r:
                print(row['first_name'])
                print(session.attributes['guest_name'])
                if row['first_name'].lower() == session.attributes['guest_name'].lower():
                    print("Code got to this point")
                    row['music_cat'] = session.attributes['eventbrite_cat']
                    row['music_cat_id'] = session.attributes['eventbrite_sub']
                    print(row['music_cat'])
                w.writerow(row)
        tempfile.seek(tempfile.tell() - len(os.linesep))
        tempfile.truncate()
    shutil.move(tempfile.name, filename)

    # RETURN PREVIEW URL FROM SPOTIFY
    top_track_query = spot.artist_top_tracks(artist_id=artist_id_str)
    preview_urls = [e['preview_url'] for e in top_track_query['tracks']]
    for x in preview_urls:
        if x is not None:
            return x

@ask.intent("NoIntent")
def close():
    closing_msg = render_template('closing')
    return statement(closing_msg)


@ask.intent('AMAZON.StopIntent')
def stop():
    return audio('stopping').clear_queue(stop=True)


@ask.intent('AMAZON.PauseIntent')
def pause():
    return audio('Paused the stream.').stop()


@ask.intent('AMAZON.ResumeIntent')
def resume():
    return audio('Resuming.').resume()

if __name__ == '__main__':
    app.run(debug=True)