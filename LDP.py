from flask import Flask, render_template
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
    return render_template('subcategories.html',subcategory_name=subcategory_name)

if __name__ == '__main__':
    app.run()
