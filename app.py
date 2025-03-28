from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
db = SQLAlchemy(app)

# Ensure the upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(256), nullable=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.String(150), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    year = db.Column(db.String(4), nullable=False)
    class_name = db.Column(db.String(10), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Integer, nullable=True)
    contact = db.Column(db.String(15), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('posts', lazy=True))

@app.route('/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password=hashed_password)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        except:
            flash('User already exists!', 'danger')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['username'] = username
            flash('Login successful!', 'success')            
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'username' not in session:
        flash('You need to log in to access the home page.', 'danger')
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()
    return render_template('index.html', user=user)

@app.context_processor
def inject_user():
    if 'username' in session:
        user = User.query.filter_by(username=session['username']).first()
        return {'current_user': user}
    return {'current_user': None}

@app.route('/createpost', methods=['GET', 'POST'])
def createpost():
    if 'username' not in session:
        flash('You need to be logged in to create a post.', 'danger')
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()
    if not user:
        flash('User not found. Please log in again.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        year = request.form.get('year')
        class_name = request.form.get('class')
        description = request.form.get('description')
        price = request.form.get('price')
        amount = request.form.get('amount') if price == 'Paid' else None
        contact = request.form.get('contact')

        # Handle image uploads
        files = request.files.getlist('book_images')
        filenames = []
        for file in files:
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                filenames.append(filename)

        # Save the post to the database
        try:
            new_post = Post(
                title=title,
                year=year,
                class_name=class_name,
                description=description,
                price=price,
                amount=amount,
                contact=contact,
                image=','.join(filenames),  # Save image filenames as a comma-separated string
                user_id=user.id
            )
            db.session.add(new_post)
            db.session.commit()
            flash('Post created successfully!', 'success')
            return redirect(url_for('viewposts'))
        except Exception as e:
            print(e)
            flash('An error occurred while creating the post.', 'danger')

    return render_template('createpost.html')

@app.route('/viewposts')
def viewposts():
    posts = Post.query.all()
    for post in posts:
        # Ensure only the first image is passed to the template
        post.image = post.image.split(',')[0] if ',' in post.image else post.image
    return render_template('viewposts.html', posts=posts)

@app.route('/viewpost/<int:post_id>')
def viewpost(post_id):
    post = Post.query.get_or_404(post_id)
    images = post.image.split(',')  # Split the filenames into a list
    return render_template('viewpost.html', post=post, images=images)

@app.route('/settings')
def settings():
    if 'username' not in session:
        flash('You need to be logged in to access settings.', 'danger')
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()
    posts = Post.query.filter_by(user_id=user.id).all()
    for post in posts:
        # Ensure only the first image is passed to the template
        post.image = post.image.split(',')[0] if ',' in post.image else post.image
    return render_template('settings.html', posts=posts)

@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    try:
        # Delete associated images
        if post.image:
            image_list = post.image.split(',')  # Split the image filenames
            for image in image_list:
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], image)
                if os.path.exists(image_path):
                    os.remove(image_path)  # Delete the image file

        # Delete the post from the database
        db.session.delete(post)
        db.session.commit()
        flash('Post and associated images deleted successfully!', 'success')
    except Exception as e:
        print(e)
        flash('An error occurred while deleting the post.', 'danger')
    return redirect(url_for('settings'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
