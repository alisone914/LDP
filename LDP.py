from flask import Flask
from eventbrite import Eventbrite

app = Flask(__name__)
with open(r'..\eventbrite_token') as fd:
    token = fd.read().strip()

@app.route('/')
def hello_world():
    return 'Hello World!'

@app.route('/user')
def user():
    eventbrite = Eventbrite(token)
    user = eventbrite.get_user()
    return user['id']


if __name__ == '__main__':
    app.run()
