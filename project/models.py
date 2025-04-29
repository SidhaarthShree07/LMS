from flask_login import UserMixin
from enum import Enum
from . import db
from datetime import datetime

class UserRole(Enum):
    SUPER_ADMIN = 'super_admin'
    LIBRARIAN = 'librarian'
    USER = 'user'
    
class Status(Enum):
    AVAILABLE = 'available'
    NOT_AVAILABLE = 'not_available'
    PENDING = 'pending'
    
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True) 
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(300))
    name = db.Column(db.String(1000))
    role = db.Column(db.Enum(UserRole), default=UserRole.USER)
    dob = db.Column(db.Date, nullable=True)
    image_filename = db.Column(db.Text, nullable=True)
    class_year = db.Column(db.Integer, nullable=True)
    email = db.Column(db.String(255), nullable=True)
    mobile_no = db.Column(db.String(20), nullable=True)
    remember_token = db.Column(db.String(128), nullable=False, default='')
    issued_books = db.relationship('IssueBooks', lazy=True, cascade='all, delete-orphan', back_populates='user', overlaps="books_issued")
    cart_books = db.relationship('Cart', lazy=True, cascade='all, delete-orphan', back_populates='user', overlaps="books_in_cart")
    user_comments = db.relationship('Comment', lazy=True, cascade='all, delete-orphan', overlaps="comments_user")
    ratings_given = db.relationship('Rating', back_populates='user', lazy=True, overlaps="ratings")
    
    def __repr__(self):
        return f"User('{self.username}')"
    
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text)
    section_id = db.Column(db.Integer, db.ForeignKey('section.id'), nullable=True)
    copies_available = db.Column(db.Integer, nullable=False, default=0)
    popularity = db.Column(db.Integer, nullable=False, default=0)
    image_filename = db.Column(db.Text)
    pdf_filename = db.Column(db.Text)
    uploaded_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    price = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.Enum(Status), default=Status.AVAILABLE)
    audio_file = db.Column(db.Text)
    
    issues = db.relationship('IssueBooks', lazy=True, cascade='all, delete-orphan', back_populates='book', overlaps="issued_to")
    issue_his = db.relationship('IssueHistory', lazy=True, cascade='all, delete-orphan', back_populates='book', overlaps="issued_to_User")
    cart_books = db.relationship('Cart', lazy=True, cascade='all, delete-orphan', back_populates='book', overlaps="cart_to")
    comments = db.relationship('Comment', lazy=True, cascade='all, delete-orphan')
    ratings = db.relationship('Rating', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"Book('{self.title}', '{self.author}')"
    
class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    description = db.Column(db.Text)
    color = db.Column(db.String(100), nullable=False)

    books = db.relationship('Book', backref='section', lazy=True)

    def __repr__(self):
        return f"Section('{self.name}')"
    
class IssueBooks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    issue_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    return_date = db.Column(db.DateTime)
    status = db.Column(db.String(100), nullable=False) 

    book = db.relationship('Book', back_populates='issues', lazy=True, overlaps="issued_to")
    user = db.relationship('User', back_populates='issued_books', lazy=True, overlaps="books_issued")
    def __repr__(self):
        return f"IssueBooks('{self.book_id}', '{self.user_id}', '{self.issue_date}', '{self.return_date}')"

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    book = db.relationship('Book', back_populates='cart_books', lazy=True, overlaps="cart_to")
    user = db.relationship('User', back_populates='cart_books', lazy=True, overlaps="books_in_cart")

    def __repr__(self):
        return f"Cart('{self.book_id}', '{self.user_id}')"

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='comments_user', lazy=True,overlaps="user_comments")  
    book_id = db.Column(db.Integer, db.ForeignKey('book.id', ondelete='CASCADE'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id', ondelete='CASCADE'), nullable=False)
    book = db.relationship('Book', backref=db.backref('book_ratings', lazy=True),overlaps="ratings")  
    user = db.relationship('User', back_populates='ratings_given', lazy=True, overlaps="ratings")
    stars = db.Column(db.Integer, nullable=False)
    date_rated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"Rating('{self.user_id}', '{self.book_id}', '{self.stars}')"

class IssueHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    issue_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    return_date = db.Column(db.DateTime)

    book = db.relationship('Book', backref='issued_to_User', lazy=True)
    user = db.relationship('User', backref='books_issued_History', lazy=True)  
    def __repr__(self):
        return f"IssueHistory('{self.book_id}', '{self.user_id}', '{self.issue_date}', '{self.return_date}')"
