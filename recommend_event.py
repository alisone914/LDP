import csv
import io
import logging
import os
import urllib

import googlemaps
import psycopg2
import spotipy
import twilio.rest
from eventbrite import Eventbrite
from flask import Flask, make_response, render_template
from flask_ask import Ask, audio, question, session, statement
from spotipy.oauth2 import SpotifyClientCredentials


app = Flask(__name__)
ask = Ask(app, "/ask")
logging.getLogger("flask_ask").setLevel(logging.DEBUG)
reprompt_txt = "I didn't get that, "


def get_key(api_source):
    var = os.environ.get(api_source)
    if not var:
        with io.open('api_keys.csv', 'r') as f:
            r = csv.DictReader(f, fieldnames=("api_source", "api_key"))
            for row in r:
                if row['api_source'] == api_source:
                    var = row['api_key']
    return var


@ask.launch
def new_interaction():
    welcome_msg = render_template('welcome')
    reprompt_welcome_msg = render_template('reprompt welcome')
    return question(welcome_msg) \
        .reprompt(reprompt_txt + reprompt_welcome_msg)


@ask.intent("RoomIntent", convert={'room_number': int})
def store_room_number(room_number):
    session.attributes['room_number'] = room_number
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT first_name, last_name, hotel, phone, genre, genre_id
                FROM guests WHERE id=%s
                """, (room_number,))
            row = cursor.fetchone()
            guest_name = row[0]
            session.attributes['guest_name'] = guest_name
            session.attributes['hotel'] = row[2]
            session.attributes['phone_number'] = row[3]
            session.attributes['music_cat'] = row[4]
            session.attributes['music_cat_id'] = row[5]
    conn.close()
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
    desired_time_var = desired_time.replace(" ", "_")
    session.attributes['desired_time_speak'] = desired_time
    session.attributes['desired_time'] = desired_time_var
    checking_msg = render_template('event check', desired_time=desired_time)
    return question(checking_msg)


@ask.intent("SatisfactionIntent", convert={'satisfaction_response': str})
def generate_recommendations(satisfaction_response):
    event = get_recommendation(session.attributes['desired_time'])
    if not event:
        desired_time = session.attributes['desired_time_speak']
        no_event = render_template('no event', desired_time=desired_time)
        return question(no_event)
    recommendation_msg = render_template('recommendation', event=event)
    return statement(recommendation_msg)


def get_recommendation(desired_time):
    # GET EVENT RECOMMENDATION FROM EVENTBRITE

    # GET EVENTBRITE API KEY
    eventbrite_api_key = get_key('EVENTBRITE_TOKEN')
    eventbrite = Eventbrite(eventbrite_api_key)

    # GET ADDRESS FROM HOTEL NAME (GOOGLEMAPS)
    google_api_key = get_key('GOOGLE')
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
    if not eventnames:
        return False
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

    eventlist = zip(eventkeys, eventnames, eventnames, eventlogo)

    eventstart = [l['local']
                  for l in (e['start'] for e in eventquery['events'])]
    start1 = eventstart[0]

    eventend = [l['local'] for l in (e['end'] for e in eventquery['events'])]
    end1 = eventend[0]

    eventvenue = [v['venue_id'] for v in eventquery['events']]
    venue1 = eventvenue[0]
    venuequery = eventbrite.get('/venues/{0}'.format(venue1))
    venue_list = venuequery['address']['localized_multi_line_address_display']
    venue_string = " ".join(str(x) for x in venue_list)

    eventurl = [u['url'] for u in eventquery['events']]
    url1 = eventurl[0]

    # CREATE EVENT TERMS

    eventterms = []
    for i in eventnames:
        eventterms.append((((category_input + '__' + session.attributes['music_cat']).replace(" ", "_")).replace("/", "and")).lower())

    termfile = zip(eventkeys, eventterms)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany("""
                INSERT INTO products (id, name, description, image_link)
                VALUES (%s, %s, %s, %s)
                """, eventlist)
            cursor.executemany("""
                INSERT INTO terms (event_key, event_term) VALUES (%s, %s)
                """, termfile)
    conn.close()

    # TEXT EVENT DETAILS

    account_sid = get_key('TWILIO_SID')
    auth_token = get_key('TWILIO_TOKEN')

    client = twilio.rest.Client(account_sid, auth_token)

    client.messages.create(
        to=session.attributes['phone_number'],
        from_=get_key('TWILIO_PHONE'),
        body="Your IHG Concierge has sent you an event you may enjoy: " +
             '\n' + event1 + '\n' + descr1[:800] + '\n' + "Start Time: " +
             start1 + '\n' + "End Time: " + end1 + '\n' + "Venue: " +
             venue_string + '\n' + url1,
        media_url=logo1)

    return eventnames[0]


def get_url(artist_request):

    # USE SPOTIFY CLIENT CREDENTIALS FROM API KEYS FILE
    spotify_client_id = get_key('SPOTIFY_CLIENT_ID')
    spotify_client_secret = get_key('SPOTIFY_CLIENT_SECRET')
    client_credentials_manager = \
        SpotifyClientCredentials(client_id=spotify_client_id,
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
        try:
            found_cat_map
        except NameError:
            session.attributes['eventbrite_cat'] = primary_genre
            session.attributes['eventbrite_sub'] = 'check genre'
            session.attributes['category_map_error'] = \
                ["Check category map: " + primary_genre]
            # with open('errors.txt', 'a') as f:
            #     w = csv.writer(f)
            #     w.writerow(session.attributes['category_map_error'])

    # UPDATE TERMS FILE WITH ARTIST GENRES
    file_genres = []
    for x in artist_genres:
        file_genres.append(('music__' + x).replace(" ", "_").replace("-", "_").lower())
    file_genres.append(('music__' + session.attributes['eventbrite_cat']).replace(" ", "_").replace("-", "_").lower())

    artistset = []
    for i in file_genres:
        artistset.append(('music-' + artist_request).replace(" ", "-").replace("/", "and").lower())

    artisttags = zip(artistset, file_genres)

    # UPDATE TRANSACTIONS FILE WITH MUSIC INTERACTION
    transactions = []
    transactions.insert(0, "")
    transactions.insert(1, session.attributes['guest_name'].lower())
    transactions.insert(2, ('music-' + artist_request).replace(" ", "-").lower())
    transactions.insert(3, '1')
    transactions = [transactions, ]

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany("""
                INSERT INTO terms (event_key, event_term) VALUES (%s, %s)
                """, artisttags)
            cursor.executemany("""
                INSERT INTO transactions (ts, guest, term, count)
                VALUES (%s, %s, %s, %s)
                """, transactions)
            cursor.execute("""
                UPDATE guests SET genre=%s, genre_id=%s
                WHERE lower(first_name)=%s
                """, (session.attributes['eventbrite_cat'],
                      session.attributes['eventbrite_sub'],
                      session.attributes['guest_name'].lower()))
    conn.close()

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


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/terms')
def terms():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT * FROM terms""")
            terms = cursor.fetchall()
    conn.close()

    def format(term):
        return term.replace(" ", "_") \
                   .replace("-", "_") \
                   .replace('&', '_and_').lower()

    formatted_terms = [(t[0], format(t[1])) for t in terms]
    return send_tsv(formatted_terms, 'terms')


@app.route('/transactions')
def transactions():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT * FROM transactions""")
            transactions = cursor.fetchall()
    conn.close()
    return send_tsv(transactions, 'transactions')


@app.route('/products')
def products():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT * FROM products""")
            products = cursor.fetchall()
    conn.close()
    formatted_products = [(p[0], p[1], p[2], '', p[3])
                          for p in products]
    return send_tsv(formatted_products, 'products')


@app.route('/guests')
def guests():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""SELECT * FROM guests""")
            guests = cursor.fetchall()
    conn.close()
    return send_tsv(guests, 'guests')


def send_tsv(rows, filename):
    f = io.StringIO()
    w = csv.writer(f, delimiter='\t')
    w.writerows(rows)
    output = make_response(f.getvalue())
    output.headers['Content-Disposition'] = \
        'attachment; filename=%s.tsv' % filename
    output.headers['Content-type'] = 'text/tab-separated-values'
    return output


def table_exists(conn, table_name):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
             SELECT 1 FROM information_schema.tables
             WHERE table_schema = 'public'
              AND table_name = %s)
            """, (table_name,))
        return bool(cursor.fetchone()[0])


def get_connection():
    urllib.parse.uses_netloc.append("postgres")
    url = urllib.parse.urlparse(get_key('DATABASE_URL'))

    conn = psycopg2.connect(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port
    )
    return conn


@app.before_first_request
def run_on_start():
    with get_connection() as conn:
        if not table_exists(conn, 'terms'):
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE terms (event_key text, event_term text)
                    """)
        if not table_exists(conn, 'products'):
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE products
                     (id text, name text, description text,
                      image_link text)
                    """)
        if not table_exists(conn, 'transactions'):
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE table transactions
                     (ts text, guest text, term text, count int)
                    """)
        if not table_exists(conn, 'guests'):
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE table guests
                     (id serial primary key, first_name text,
                      last_name text, hotel text, phone text,
                      genre text, genre_id int)
                    """)
    conn.close()


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
