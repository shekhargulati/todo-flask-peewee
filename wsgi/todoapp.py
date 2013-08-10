import os
import datetime
from flask import Flask, flash, redirect, request, render_template, url_for
import peewee as pw
import wtforms as wt
from flask_peewee.auth import Auth
from flask_peewee.auth import BaseUser
from flask_peewee.db import Database
from utils import slugify

DEBUG = True
SECRET_KEY = 'test_secret_key'

app = Flask(__name__)
#app.config.from_object(__name__)
db = pw.PostgresqlDatabase(os.environ['OPENSHIFT_APP_NAME'], user=os.environ['OPENSHIFT_POSTGRESQL_DB_USERNAME'], password=os.environ['OPENSHIFT_POSTGRESQL_DB_PASSWORD'] ,'host'= os.environ['OPENSHIFT_POSTGRESQL_DB_HOST'],
    'port'= os.environ['OPENSHIFT_POSTGRESQL_DB_PORT'],)
auth = Auth(app, db)

class PostgresqlModel(db.Model):
    """A base model that will use our Postgresql database"""
    class Meta:
        database = db


# Models
class User(PostgresqlModel):
    # whatever fields

    class Meta:
        db_table = 'users' # <-- set explicitly right here


class Task(PostgresqlModel):
    task = pw.TextField()
    user = pw.ForeignKeyField(User)
    created = pw.DateTimeField(default=datetime.datetime.now)
    due = pw.DateField()

    @property
    def tags(self):
        return Tag.select().join(TaskTag).join(Task).where(Task.id == self.id)


class Tag(PostgresqlModel):
    tag = pw.TextField(unique=True)


class TaskTag(PostgresqlModel):
    task = pw.ForeignKeyField(Task)
    tag = pw.ForeignKeyField(Tag)


# Forms
class TaskForm(wt.Form):
    task = wt.TextField([wt.validators.Required()])
    tags = wt.TextField()
    due = wt.DateField()


# Queries
def user_tasks():
    return Task.select().join(User).where(User.id == auth.get_logged_in_user())


def user_tagged_tasks(tag):
    tagged_tasks = TaskTag.select().join(Tag).where(Tag.tag == tag)
    #XXX:Join jiu jitsu fail.
    tasks = Task.select().join(User).where(
        (User.id == auth.get_logged_in_user()) &
        (Task.id << [t.task for t in tagged_tasks]))
    return tasks


# Views
@app.route("/", methods=['GET'])
@auth.login_required
def home():
    sortby = request.args.get('sortby', 'due')
    if sortby == 'title':
        todos = user_tasks().order_by(Task.task)
    else:
        todos = user_tasks().order_by(Task.due)
    return render_template('todo.html', todos=todos)


@app.route('/add', methods=['POST'])
@auth.login_required
def add_task():
    form = TaskForm(request.form)
    if form.validate():
        tags = [slugify(t) for t in form.tags.data.split(' ')]
        new_task = Task(task=form.task.data,
                        user=auth.get_logged_in_user(),
                        due=form.due.data
                        )
        new_task.save()
        for t in tags:
            try:
                new_tag = Tag.get(tag=t)
            except:
                new_tag = Tag(tag=t)
                new_tag.save()
            tasktag = TaskTag(task=new_task.id, tag=new_tag.id)
            tasktag.save()
        flash("New Task: %s" % (new_task.task))
    else:
        flash("Derp!")
    return redirect(url_for('home'))


@app.route('/del', methods=['POST'])
@auth.login_required
def delete_task():
    tskid = request.form['task']
    #XXX: delete only those tasks belonging to the user
    tskobj = Task.get(Task.id == tskid)
    tskobj.delete_instance()
    query = TaskTag.delete().where(TaskTag.task == tskid)
    query.execute()
    flash("Task deleted.")
    return redirect(url_for('home'))


@app.route("/tag/<tag>", methods=['GET'])
def tag(tag):
    todos = user_tagged_tasks(tag)
    flash("Tasks labeled %s" % (tag, ))
    return render_template('todo.html', todos=todos)


def create_all():
    '''create all the tables'''
    auth.User.create_table(fail_silently=True)
    Task.create_table(fail_silently=True)
    Tag.create_table(fail_silently=True)
    TaskTag.create_table(fail_silently=True)

def add_users():
    try:
        u1 = auth.User(username='admin', admin=True, active=True)
        u1.email = 'shekhargulati84@gmail.com'
        u1.set_password('secret')
        u1.save()
        u2 = auth.User(username='shekhargulati', admin=True, active=True)
        u2.email = 'shekhargulati@yahoo.com'
        u2.set_password('password')
        u2.save()
    except Exception, e:
        pass

if __name__ == '__main__':
    create_all()
    add_users()
    app.run()
