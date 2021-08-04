from logging import error
import re
import functools
from flask import Flask, render_template, redirect, request, url_for, flash, g, session
from flask.globals import current_app
from flask_mysqldb import MySQL
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import abort

app = Flask(__name__)
app.config['MYSQL_HOST'] = 'bo1jvbdembwyvpaqpiwg-mysql.services.clever-cloud.com'
app.config['MYSQL_USER'] = 'ugij9fnhzsije25s'
app.config['MYSQL_PASSWORD'] = 'zPQIm6VxA9b8gbN3jYR5'
app.config['MYSQL_DB'] = 'bo1jvbdembwyvpaqpiwg'
mysql = MySQL(app)

app.secret_key = 'Esto_Debe_Ser_Secreto'

@app.route('/')
def index():
    cur = mysql.connection.cursor()
    cur.execute("SELECT p.id, title, body, created, author_id, username FROM post p JOIN users u ON p.author_id = u.id ORDER BY created DESC")
    posts = cur.fetchall()
    return render_template('blog/blog-post-list.html', posts=posts)

@app.route('/signup', methods=('GET', 'POST'))
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        rol = "2"
        error = None
        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE username LIKE %s", [username])
        id = cur.fetchone()
        if not username:
            error = 'Username is required'
        elif not password:
            error = 'Password is required'
        elif id is not None:
            error = f"User {username} is already registered"
        if error is None:
            cur.execute("INSERT INTO users (username, password, rol_id) VALUES (%s, %s, %s)", (username, generate_password_hash(password), rol))
            mysql.connection.commit()
            return redirect(url_for('login'))
        flash(error)
    return render_template('auth/signup.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username LIKE %s", [username])
        user = cur.fetchone()
        if not username:
            error = 'Username is required'
        elif not password:
            error = 'Password is required'
        elif user[1] != username:
            error = 'Incorrect username'
        elif not check_password_hash(user[2], password):
            error = 'Incorrect password'
        if error is None:
            session.clear()
            session['user_id'] = user[0]
            return redirect(url_for('index'))
        flash(error)
    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE id LIKE %s", [user_id])
        g.user = cur.fetchone()

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user[3] != 1:
            return redirect(url_for('index'))
        return view(**kwargs)
    return wrapped_view

@app.route('/admin/users')
@admin_required
def load_registered_users():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    return render_template('admin/users.html', users=users)

def get_user(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id LIKE %s", [id])
    data = cur.fetchone()
    return data

@app.route('/admin/users/update/<string:id>', methods=('GET', 'POST'))
@admin_required
def update_user(id):
    data = get_user(id)
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None
        cur = mysql.connection.cursor()
        cur.execute("SELECT username FROM users WHERE username LIKE %s", [username])
        name = cur.fetchone()
        if not username:
            error = 'Username is required'
        elif not password:
            error = 'Password is required'
        elif name is not None:
            if name[0] != data[1]:
                error = f"User {username} is already registered"
        if error is not None:
            flash(error)
        else:
            cur.execute("UPDATE users SET username = %s, password = %s WHERE id = %s", (username, generate_password_hash(password), id))
            mysql.connection.commit()
            return redirect(url_for('load_registered_users'))
    return render_template('/admin/edit-user.html', user=data)

@app.route('/admin/users/delete/<string:id>')
@admin_required
def delete_user(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM post WHERE author_id LIKE %s", [id])
    mysql.connection.commit()
    cur.execute("DELETE FROM users WHERE id LIKE %s", [id])
    mysql.connection.commit()
    return redirect(url_for('load_registered_users'))

@app.route('/post/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        post = request.form['post']
        error = None
        if not title:
            error = 'Title is required.'
        if error is not None:
            flash(error)
        else:
            cur = mysql.connection.cursor()
            cur.execute('INSERT INTO post (title, body, author_id) VALUES(%s, %s, %s)', (title, post, g.user[0]))
            mysql.connection.commit()
            return redirect(url_for('index'))
    return render_template('blog/blog-post-create.html')

def get_post(id, check_author=True):
    cur = mysql.connection.cursor()
    cur.execute("SELECT p.id, title, body, created, author_id, username FROM post p JOIN users u ON p.author_id = u.id WHERE p.id = %s", [id])
    post = cur.fetchone()
    if post is None:
        abort(404, f"Post id {id} doesn't exist")
    if check_author and post[4] != g.user[0]:
        abort(403)
    return post

@app.route('/post/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    post = get_post(id)
    if request.method == 'POST':
        title = request.form['title']
        post = request.form['post']
        error = None
        if not title:
            error = 'Title is required'
        if error is not None:
            flash(error)
        else:
            cur = mysql.connection.cursor()
            cur.execute("UPDATE post SET title = %s, body = %s WHERE id = %s", (title, post, id))
            mysql.connection.commit()
            return redirect(url_for('index'))
    return render_template('blog/blog-post-edit.html', post=post)

@app.route('/post/<int:id>/delete')
@login_required
def delete(id):
    post = get_post(id)
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM post WHERE id LIKE %s", [post[0]])
    mysql.connection.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(port=1000, debug=True)