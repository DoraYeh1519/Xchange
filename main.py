from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request, session
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import desc
import setuptools
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_migrate import Migrate
import pymysql
import zipfile
import os

# flask setup
app = Flask(__name__)
SECRET_KEY = os.urandom(32)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER')

# html setup
ckeditor = CKEditor(app)
Bootstrap5(app)

login_manager = LoginManager()
login_manager.init_app(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://root:EmeR2023@localhost:3306/dbms_project"
db = SQLAlchemy()
migrate = Migrate(app, db)
db.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.user_id != 1:
            error = 'Sorry, this page is Admin only, please log in as Admin to access'
            return redirect(url_for('login', error=error))
        return f(*args, **kwargs)

    return decorated_function


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif','zip'}


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blogpost"
    blogpost_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    upload_date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    views = db.Column(db.Integer, default=0, nullable=False)
    author_id = db.Column(db.String(250),db.ForeignKey('user.user_id'), nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    img_folder = db.Column(db.String(250), nullable=True)
    comments = db.relationship("Comment",backref="post")
    reacts = db.relationship("React", backref="post")


class User(UserMixin, db.Model):
    __tablename__ = "user"
    user_id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(200))
    email = db.Column(db.String(100), unique=True)
    profile_img_url = db.Column(db.String(1000))
    password = db.Column(db.String(100))
    posts = db.relationship("BlogPost", backref="author")
    comments = db.relationship("Comment",backref="user")
    reacts = db.relationship("React", backref="user")


class Comment(db.Model):
    __tablename__ = "comment"
    comment_id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('blogpost.post_id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.String(250), db.ForeignKey('user.user_id'), nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)

class Incoming_user(User):
    __tablename__ = "incoming_user"
    incoming_user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), primary_key=True)
    origin_school = db.Column(db.String(250),nullable = False)
    continent = db.Column(db.String(250),nullable = False)
    country = db.Column(db.String(250),nullable = False)
    region = db.Column(db.String(250),nullable = False)

    __mapper_args__ = {
        'polymorphic_identity': 'Incoming_user',
        'inherit_condition': incoming_user_id == User.user_id
    }

class Outgoing_user(User):
    __tablename__ = "outgoing_user"
    outgoing_user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), primary_key=True)
    exchanging_school = db.Column(db.String(250),nullable = False)
    continent = db.Column(db.String(250),nullable = False)
    country = db.Column(db.String(250),nullable = False)
    region = db.Column(db.String(250),nullable = False)

    __mapper_args__ = {
        'polymorphic_identity': 'Outgoing_user',
        'inherit_condition': outgoing_user_id == User.user_id
    }

class React(db.Model):
    __tablename__ = "react"
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('blogpost.post_id'), primary_key=True)

@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        error = None
        email = form.data['email']
        password = generate_password_hash(form.data['password'], method='pbkdf2:sha256', salt_length=8)
        # checking if email is already in database and referring to login page
        result = db.session.execute(db.select(User).where(User.email == email))
        existing_user = result.scalar()
        if existing_user:
            error = "Sorry, this email already exists, try logging inx instead:"
            return redirect(url_for('login', error=error))

        # Save the uploaded image to the server
        img_file = form.img_url.data
        if img_file and allowed_file(img_file.filename):
            filename = secure_filename(img_file.filename)
            img_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            img_url = filename
        else:
            img_url = None

        new_user = User(
            user_id=form.data['user_id'],
            user_name=form.data['user_name'],
            email=email,
            password=password,
            img_url=img_url
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    error = request.args.get('error')
    form = LoginForm()
    if form.validate_on_submit():
        email = form.data['email']
        password = form.data['password']

        # Find user by email entered.
        result = db.session.execute(db.select(User).where(User.email == email))
        user = result.scalar()
        if not user:
            error = "E-mail not found. If you don't have an account, register instead."
        elif not check_password_hash(user.password, password):
            error = 'Wrong password, please try again'
        else:
            login_user(user)
            flash('You were successfully logged in')
            return redirect(url_for('get_all_posts'))
    print(error)
    return render_template("login.html", error=error, form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost).order_by(desc(BlogPost.blogpost_id)))
    posts = result.scalars().all()
    # Check if there are any posts
    if len(posts) == 0:
        # If no posts are available, render a template indicating that there are no posts.
        return render_template("no_posts.html")
    return render_template("index.html", all_posts=posts)


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    form = CommentForm()

    if form.validate_on_submit():
        new_comment = Comment(
            comment=form.data['comment'],
            post_id=requested_post.blogpost_id,
            author=current_user.user_name,
            img_url=current_user.img_url,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for("show_post", post_id=post_id))

    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.comment_id.desc()).all()
    image_files = []

    if requested_post.img_folder:
        img_folder_path = requested_post.img_folder
        # Get list of directory names (gallery names) in the img_folder_path
        gallery_names = os.listdir(img_folder_path)

        # Iterate over each gallery and get the list of filenames within each gallery
        for gallery_name in gallery_names:
            gallery_path = os.path.join(img_folder_path, gallery_name)
            if os.path.isdir(gallery_path):
                filenames = os.listdir(gallery_path)
                # Extend the image_files list with filenames within this gallery
                image_files.extend(filenames)

    return render_template("post.html", post=requested_post, form=form,
                           all_comments=comments, image_files=image_files, post_id=str(post_id))


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        # Save uploaded folder to server
        images_folder = form.images_folder.data
        if images_folder:
            # Ensure that the uploaded file has a valid extension
            if not allowed_file(images_folder.filename):
                flash("File does not have an approved extension.")
                return redirect(url_for("add_new_post"))

            folder_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(images_folder.filename))
            images_folder.save(folder_path)
            # Extract the uploaded zip file
            extract_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'extracted')
            os.makedirs(extract_folder, exist_ok=True)  # Create folder if not exists
            try:
                with zipfile.ZipFile(folder_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_folder)
            except zipfile.BadZipFile:
                flash('Error: Uploaded file is not a valid zip file.')
                os.remove(folder_path)  # Remove the uploaded zip file
                return redirect(url_for("add_new_post"))
            image_files = os.listdir(extract_folder)
        else:
            extract_folder = None
            image_files = []

        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            img_folder=extract_folder,  # Set the extracted folder path
            author=current_user.user_name,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(obj=post)
    if edit_form.validate_on_submit():
        images_folder = edit_form.images_folder.data
        if images_folder:
            # Ensure that the uploaded file has a valid extension
            if not allowed_file(images_folder.filename):
                flash("File does not have an approved extension.")
                return redirect(url_for("add_new_post"))

            folder_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(images_folder.filename))
            images_folder.save(folder_path)
            # Extract the uploaded zip file
            extract_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'extracted')
            os.makedirs(extract_folder, exist_ok=True)  # Create folder if not exists
            try:
                with zipfile.ZipFile(folder_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_folder)
            except zipfile.BadZipFile:
                flash('Error: Uploaded file is not a valid zip file.')
                os.remove(folder_path)  # Remove the uploaded zip file
                return redirect(url_for("add_new_post"))
            image_files = os.listdir(extract_folder)
        else:
            extract_folder = None
            image_files = []


        post.title = edit_form.title.data
        post.img_url = edit_form.img_url.data
        post.author_id = current_user.user_name
        post.img_folder = extract_folder
        post.body = edit_form.body.data

        db.session.commit()

        # Redirect to the post view page with the updated post object
        return redirect(url_for("show_post", post_id=post.blogpost_id))

    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/delete/<int:comment_id>/<int:post_id>")
@admin_only
def delete_comment(comment_id, post_id):
    comment_to_delete = db.get_or_404(Comment, comment_id)
    db.session.delete(comment_to_delete)
    db.session.commit()
    return redirect(url_for("show_post", post_id=post_id))


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=False)
