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

@app.route('/categories')
def categories():
    eventbrite = Eventbrite(token)
    category_list = eventbrite.get_categories()
    print(category_list)
    names = [category['name'] for category in category_list['categories']]
    print(names)
    return "test"

@app.route('/subcategories')
def subcategories():
    eventbrite = Eventbrite(token)
    subcategory_list = eventbrite.get_subcategories()
    print(subcategory_list)
    subcategory_name = [subcategory['name'] for subcategory in subcategory_list['subcategories']]
    print(subcategory_name)
    return '''
    <html>
      <head>
        <title>Intuitive Guest Experiences Platform</title>
      </head>
      <body>
        <h1>subcategory_list</h1>
      </body>
    </html>
    '''

if __name__ == '__main__':
    app.run()
