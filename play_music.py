import csv
import io
import logging
from flask import Flask, render_template
from flask_ask import Ask, request, session, question, statement, context, audio, current_stream
import spotipy

app = Flask(__name__)
ask = Ask(app, "/")
logging.getLogger("flask_ask").setLevel(logging.DEBUG)


@ask.launch
def new_interaction():
    welcome_msg = render_template('welcome')
    return question(welcome_msg)

@ask.intent("RoomIntent",  convert={'room_number': int})
def store_room_number(room_number):
    session.attributes['room_number'] = room_number
    room_number = str(room_number)
    with io.open('guests.csv', 'r') as f:
        r = csv.DictReader(f, fieldnames=("room_number", "first_name", "last_name", "hotel"))
        for row in r:
            file_room_number = row['room_number']
            if file_room_number == room_number:
                guest_name = row['first_name']
    offer_msg = render_template('music offer', guest_name=guest_name)
    return question(offer_msg)


@ask.intent("PlayAudio", convert={'guest_artist': str})
def play_audio(guest_artist):
    spot = spotipy.Spotify()
    session.attributes['guest_artist'] = guest_artist
    artist_request = guest_artist
    artistquery = spot.search(q=artist_request, type='artist')

    artist_id = [e['id'] for e in artistquery['artists']['items']]
    artist_id_str = ''.join(artist_id[0])

    artist_genres = [g for g in (e['genres'] for e in artistquery['artists']['items'])]
    artist_genres = artist_genres[0]

    primary_genre = artist_genres[0]
    print(primary_genre)

    file_genres = []
    for x in artist_genres:
        file_genres.append(('music__' + x).replace(" ", "_"))
    print(file_genres)

    artistset = []
    for i in file_genres:
        artistset.append(('music-' + artist_request).replace(" ", "-"))
    print(artistset)

    artisttags = zip(artistset, file_genres)
    print(artisttags)

    with open('terms.tsv', 'a') as f:
        w = csv.writer(f, delimiter='\t')
        for i in artisttags:
            w.writerow(i)

    top_track_query = spot.artist_top_tracks(artist_id=artist_id_str)

    preview_urls = [e['preview_url'] for e in top_track_query['tracks']]

    for x in preview_urls:
        if x != None:
            stream_url = x
            break

    speech = "Here's one of my favorites"
    return audio(speech).play(stream_url, offset=0)


@ask.intent('AMAZON.PauseIntent')
def pause():
    return audio('Paused the stream.').stop()


@ask.intent('AMAZON.ResumeIntent')
def resume():
    return audio('Resuming.').resume()


@ask.intent('AMAZON.StopIntent')
def stop():
    return audio('stopping').clear_queue(stop=True)

if __name__ == '__main__':
    app.run(debug=True)