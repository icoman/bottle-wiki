"""

    Wiki webserver with bottlepy, markdown and sqlalchemy

"""

import os, datetime, re

import bottle
from sqlalchemy import create_engine
from bottle.ext import sqlalchemy
from beaker.middleware import SessionMiddleware
import markdown

from modeldb import Base, WikiPages, WikiVersions, Users, addUsers, addPages

#some useful links for wiki
internal_links = ('/edit', '/login', '/logout', '/info')

#cookie session
SESSION_NAME = os.getenv('SESSION_NAME','bottleserver.session')
COOKIE_CRYPT_KEY = os.getenv("COOKIE_CRYPT_KEY","123-456-789")
session_opts = {
    'session.cookie_expires': 24*60*60, #in seconds -> 24 hours
    'session.auto': True, # When set, calling the save() method is no longer required, and the session will be saved automatically anytime its accessed during a request.
    'session.key':SESSION_NAME,
}

current_dir = os.path.dirname(__file__)
static_folder = os.path.join(current_dir,'static')
template_folder = os.path.join(current_dir,'templates')
bottle.TEMPLATE_PATH.insert(0,template_folder)


#database connect string
#DSN = 'sqlite:///:memory:'
#DSN = 'sqlite:///%s/wiki.db' % (current_dir)
#DSN = 'postgresql://ioan:***@localhost:5432/wiki'
#DSN = 'mssql://ioan:123@localhost/wiki'
#DSN = 'mssql+pymssql://ioan:123@localhost\sqlexpress/wiki'
DSN = os.getenv('DSN','sqlite:///wiki.db')


app = bottle.Bottle()
plugin = sqlalchemy.Plugin(
    create_engine(DSN, echo=False), # SQLAlchemy engine created with create_engine function.
    Base.metadata, # SQLAlchemy metadata, required only if create=True.
    keyword='db', # Keyword used to inject session database in a route (default 'db').
    create=True, # If it is true, execute `metadata.create_all(engine)` when plugin is applied (default False).
    commit=True, # If it is true, plugin commit changes after route is executed (default True).
    use_kwargs=True # If it is true and keyword is not defined, plugin uses **kwargs argument to inject session database (default False).
)
app.install(plugin)



def js_redirect(location):
    return '<html><script>location.href="%s";</script></html>' % (location)

def auth(fn):
    """
        On every call the user send a cookie
        If it is the right cookie, then is authenticated, else redirect to login
    """
    def check_uid(**kwargs):
        #print "Authentication:",kwargs
        db = kwargs.get('db')
        path = kwargs.get('path')
        if not path.startswith('/'):
            path = '/'+path
        user = bottle.request.get_cookie('account', secret=COOKIE_CRYPT_KEY)
        if 0 == db.query(Users).count():
            #populate table with some users
            addUsers(db)
        #Password is not inside the cookie. The cookie is valid if password is correct in login form.
        if db.query(Users).filter(Users.username == user).count() > 0:
            return fn(**kwargs)
        else:
            return js_redirect("/login?back="+path)
    return check_uid


def matchLink(match, db):
    '''
        Add class "nf" to dead links or non existent wiki pages
        nf=not found
    '''
    group = match.group(0)
    link = group[6:]
    PageExists = False
    if link.startswith('http'):
        PageExists = True
    else:
        if not link.startswith('/'):
            link = '/'+link
        if link == '/':
            PageExists = True
        for i in internal_links:
            if link.startswith(i):
                PageExists = True
                break
        if 0 < db.query(WikiPages).filter(WikiPages.path == link).count():
            PageExists = True
    if PageExists:
        return group
    else:
        return group + '" class="nf' 





#
#webserver methods
#

@app.route('/')
def callback():
    return js_redirect("/FrontPage")

@app.route('/info')
def callback():
    return 'Info wiki page - <a href="/">Home</a>'

@app.route('/static/<path:path>')
def callback(path):
    return bottle.static_file(path,root=static_folder)

@app.route('/add/<path:path>',method=['GET','POST'])
@bottle.view('editpage')
@auth
def callback(db, path):
    '''
        Add wiki page
    '''
    pagepath = u'/'+path
    action = bottle.request.forms.action
    title = bottle.request.forms.title
    body = bottle.request.forms.body
    user = bottle.request.get_cookie('account', secret=COOKIE_CRYPT_KEY)
    obuser = db.query(Users).filter(Users.username == user).one()
    if action:
        if action == "Save":
            #create page + version
            page = WikiPages(pagepath, 0)
            db.add(page)
            db.commit()
            version = WikiVersions(title, body, obuser.id, page.id) 
            db.add(version)
            db.commit()
            page.version_id = version.id
            db.add(page)
            db.commit()
            return js_redirect(pagepath)
        else:
            #action is cancel
            return js_redirect("/")
    else:
        body = u"#New wiki page\n* Test\n* Hello World"
        title = u'New wiki page'
        return dict(user=user, title=title, body=body, path=path)



@app.route('/edit/<path:path>',method=['GET','POST'])
@bottle.view('editpage')
@auth
def callback(db, path):
    '''
        Edit wiki page
    '''
    pagepath = u'/'+path
    action = bottle.request.forms.action
    title = bottle.request.forms.title
    body = bottle.request.forms.body
    user = bottle.request.get_cookie('account', secret=COOKIE_CRYPT_KEY)
    page = db.query(WikiPages).filter(WikiPages.path == pagepath).one()
    version = db.query(WikiVersions).filter(WikiVersions.id == page.version_id).one()
    obuser = db.query(Users).filter(Users.username == user).one()
    if action:
        if action == "Save":
            #update page with new version
            version = WikiVersions(title, body, obuser.id, page.id) 
            db.add(version)
            db.commit()
            page.version_id = version.id
            db.add(page)
            db.commit()
        #redirect on any action
        return js_redirect(pagepath)
    else:
        body = version.body
        title = version.title
        return dict(user=user, title=title, body=body, path=path)

@app.route('/<path:path>')
@bottle.view('wikipage')
def callback(db, path):
    '''
        Return any wiki page, any version
    '''
    ver = int(bottle.request.query.get('v',0))
    user = bottle.request.get_cookie('account', secret=COOKIE_CRYPT_KEY)
    d_users = {}
    for i in db.query(Users):
        d_users[i.id] = i.username
    if 0 == db.query(WikiPages).count():
        addPages(db)
    pagepath = u'/'+path
    q = db.query(WikiPages).filter(WikiPages.path == pagepath)
    if 0 == q.count():
        return js_redirect("/add/"+path)
    else:
        page = q.one()
        allversions = db.query(WikiVersions).filter(WikiVersions.page_id == page.id).order_by(WikiVersions.created.desc()).all()
        #try to get desired version
        version = allversions[ver]
        extensions = ['markdown.extensions.codehilite','markdown.extensions.extra']
        body = markdown.markdown(version.body)
        body = re.sub(r'href=[\'"]?([^\'" >]+)', lambda ma: matchLink(ma, db), body)
        title = version.title
        pageuser = d_users.get(version.user_id,'-unknown-')
        created = version.created
        return dict(title=title, user=user, body=body, path=path, pageuser=pageuser, created=created, allversions=allversions, d_users=d_users)

@app.route('/logout')
def callback():
    bottle.response.delete_cookie("account")
    return 'Logout! <a href="/">Home</a>'

@app.route('/login', method=['GET', 'POST'])
@bottle.view('login')
def callback(db):
    title = "Login page"
    msg = ""
    back = bottle.request.forms.back #from HTML form with POST
    if not back:
        back = bottle.request.query.get('back','/') #from URL with GET
    users = []
    for i in db.query(Users):
        users.append(i.username)
    authenticated = False
    user = bottle.request.forms.user
    password = bottle.request.forms.password
    if user:
        q = db.query(Users).filter(Users.username == user)
        if q.count() > 0:
            if q.one().password == password:
                #when password is correct, set the cookie
                bottle.response.set_cookie("account", user, secret=COOKIE_CRYPT_KEY)
                authenticated = True
            else:
                msg = "Invalid password"
        else:
            msg = "Invalid user"
    if authenticated:
        return js_redirect(back)
    else:
        return dict(title=title, users=users, msg=msg, back=back)

def main():
    sess_root = SessionMiddleware(app, session_opts)
    PORT = os.environ.get('PORT',8080)
    HOST = os.environ.get('HOST','localhost')
    if os.environ.get('BOTTLE_CHILD',None):
        print "Start/Restart Server."
    else:
        print "Wiki Server: %s:%s" % (HOST,PORT)

    #bottle.run(app=sess_root, server='paste', host=HOST, port=PORT, debug=True, reloader=True)
    bottle.run(app=sess_root, server='cherrypy', host=HOST, port=PORT, debug=True, reloader=True)

if __name__ == "__main__":
    try:
        main()
    except Exception, e:
        print e
