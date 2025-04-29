from flask import Blueprint, render_template,redirect,url_for,request, abort, current_app , jsonify, send_from_directory , send_file
from flask_login import login_required, current_user
from .models import User, UserRole, Book, Section, IssueBooks, Cart, Status, Comment, Rating , IssueHistory
from . import create_app
from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, ResultReason
import azure.cognitiveservices.speech
from werkzeug.utils import secure_filename
import os
from . import db
import fitz
import zipfile
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func,text
import pytz
from azure.storage.blob import BlobServiceClient
import uuid
from datetime import datetime,timedelta
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
main = Blueprint('main', __name__)
IST = pytz.timezone('Asia/Kolkata')
baseurl = os.getenv('BASE_URL')
# Azure Blob Storage setup
AZURE_STORAGE_CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
AZURE_STORAGE_CONTAINER_NAME = os.getenv('AZURE_STORAGE_CONTAINER_NAME')

def upload_to_azure(file, filename):
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=AZURE_STORAGE_CONTAINER_NAME, blob=filename)
    blob_client.upload_blob(file, overwrite=True)
    return blob_client.url  # Return URL after upload

def update_book_status():
    books_zero_copies = Book.query.filter(Book.copies_available == 0).all()
    for book in books_zero_copies:
        book.status = Status.NOT_AVAILABLE
        
    books_with_copies = Book.query.filter(Book.copies_available > 0).all()
    for book in books_with_copies:
        book.status = Status.AVAILABLE
    db.session.commit()
    
def add_unique_issues():
    issue_books_records = IssueBooks.query.with_entities(IssueBooks.book_id, IssueBooks.user_id, IssueBooks.issue_date, IssueBooks.return_date).filter_by(status='issued').all()
    for record in issue_books_records:
        existing_record = IssueHistory.query.filter_by(
            book_id=record.book_id,
            user_id=record.user_id,
            issue_date=record.issue_date,
            return_date=record.return_date
        ).first()
        if not existing_record:
            issue_history_record = IssueHistory(book_id=record.book_id, user_id=record.user_id, issue_date=record.issue_date, return_date=record.return_date)
            db.session.add(issue_history_record)
        db.session.commit()


@main.route('/')
def index():
    add_unique_issues()
    return render_template('Home.html')

@main.route('/profile')
@login_required
def profile():
    add_unique_issues()
    if current_user.role == UserRole.SUPER_ADMIN or current_user.role == UserRole.LIBRARIAN:
        return redirect(url_for('main.librarian_dashboard'))
    else:
        return redirect(url_for('main.userprofile'))

@main.route('/libhome')
@login_required
def librarian_dashboard():
    sections = Section.query.all()
    books = Book.query.all()
    user = current_user.id
    for book in books:
        book.popularity = calculate_popularity(book)
        db.session.commit()
    update_book_status()
    add_unique_issues()
    return render_template('librarian_dashboard.html', books=books, sections=sections, user=user, baseurl=baseurl)

@main.route('/issuebook')
@login_required
def issuebook():
    issued_books = current_user.issued_books
    today_issued_books = IssueBooks.query.filter(IssueBooks.return_date <= datetime.now()).all()
    for issued_book in today_issued_books:
        book_id = issued_book.book_id
        book = Book.query.get(book_id)
        if book:
            db.session.delete(issued_book)
            book.copies_available += 1
            db.session.commit()
    return render_template('issuebook.html', issued_books=issued_books, baseurl=baseurl)

@main.route('/home')
@login_required
def userprofile():
    sections = Section.query.all()
    books = Book.query.all()
    user = current_user.id
    for book in books:
        book.popularity = calculate_popularity(book)
        db.session.commit()
    return render_template('Profile.html',name=current_user.name, books=books , sections=sections , user=user, baseurl=baseurl)

@main.route('/book/<int:id>', methods=['GET', 'POST'])
def book(id):
    book = Book.query.get(id)
    comments = Comment.query.filter_by(book_id=id).all()
    existing_ratings = Rating.query.filter_by(user_id=current_user.id, book_id=id).first() 
    avg_rating = db.session.query(func.round(func.avg(Rating.stars), 1)).filter_by(book_id=id).scalar()
    user_role = current_user.role.value
    if avg_rating == None:
        avg_rating = 0
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'issue':
            if book.status.value == "not_available":
                return render_template('book.html', book=book , comments=comments , existing_ratings=existing_ratings, baseurl=baseurl , avg_rating=avg_rating , user_role=user_role , max_books_reached=True)
            else:
                book_id = id
                status = 'pending'
                return_date = datetime.now(IST) + timedelta(days=7)
                new_issue = IssueBooks(book_id=book_id, user_id=current_user.id, issue_date=datetime.now(IST), return_date=return_date,status=status)
                db.session.add(new_issue)
                book.copies_available -= 1
                db.session.commit()
                return redirect(url_for('main.issuebook'))
        elif action == 'add_to_cart':
            print("yeah")
            existing_issue = Cart.query.filter_by(book_id=id, user_id=current_user.id).first()
            if existing_issue:
                return jsonify({'error': 'You have already have this book in Cart.'}), 400
            elif book.status.value == "not_available":
                return jsonify({'error': 'Book is Currently Unavailable.'}), 400
            else:
                book_id = id
                new_cart = Cart(book_id=book_id, user_id=current_user.id)
                db.session.add(new_cart)
                db.session.commit()
                print("done")
                return redirect(url_for('main.cart'))
    num_issued_books = IssueBooks.query.filter_by(user_id=current_user.id).count()
    if num_issued_books >= 5:
        return render_template('book.html', book=book , comments=comments , existing_ratings=existing_ratings, baseurl=baseurl , avg_rating=avg_rating , user_role=user_role , max_books_reached=True , alr_books_reached=False)
    if not book:
        abort(404)
    existing_issue = IssueBooks.query.filter_by(book_id=id, user_id=current_user.id).first()
    update_book_status()
    if existing_issue:
        return render_template('book.html', book=book , comments=comments , existing_ratings=existing_ratings, baseurl=baseurl , avg_rating=avg_rating , user_role=user_role , alr_books_reached=True)
    return render_template('book.html', book=book , comments=comments , existing_ratings=existing_ratings, baseurl=baseurl , avg_rating=avg_rating , user_role=user_role,max_books_reached=False,alr_books_reached=False)

@main.route('/read/<int:id>')
def read(id):
    read = Book.query.get(id)
    pdf_url = read.pdf_filename  # Now it will store URL, not local path

    if not read.audio_file:
        def extract_text_from_pdf(pdf_path):
            text = ""
            with fitz.open(stream=requests.get(pdf_path).content, filetype="pdf") as pdf_document:
                for page in pdf_document:
                    text += page.get_text()
            return text
        
        def text_to_speech(text, output_file_path):
            speech_config = SpeechConfig(subscription=os.getenv('AZURE_SPEECH_KEY'), region=os.getenv('AZURE_SPEECH_REGION'))
            synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=None)
            result = synthesizer.speak_text_async(text).get()
            if result.reason == ResultReason.SynthesizingAudioCompleted:
                return result.audio_data
            else:
                print("Speech synthesis failed.")
                return None

        text = extract_text_from_pdf(pdf_url)
        audio_data = text_to_speech(text, f"{id}.mp3")
        if audio_data:
            audio_filename = f"{id}.mp3"
            # Upload to Azure instead of saving locally
            upload_to_azure(audio_data, audio_filename)
            read.audio_file = audio_filename
            db.session.commit()

    return render_template('read.html', read=read, baseurl=baseurl)


@main.route('/listen-audio/<int:id>')
def listen_audio(id):
    book = Book.query.get(id)
    if not book:
        abort(404)
    audio_filename = book.audio_file
    blob_url = f"https://{os.getenv('AZURE_ACCOUNT_NAME')}.blob.core.windows.net/{AZURE_STORAGE_CONTAINER_NAME}/{audio_filename}"
    return redirect(blob_url)


@main.route('/insert')
@login_required
def insert():
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.LIBRARIAN]:
        abort(403)  

    return render_template('insert.html')

@main.route('/user/<int:user_id>')
def user_profile(user_id):
    user_role = current_user.role.value
    if current_user.role in [UserRole.SUPER_ADMIN, UserRole.LIBRARIAN]:
        pending_requests = IssueBooks.query.filter_by(status='pending').all()
        issues = IssueBooks.query.all()
        available = Book.query.all()
        user = User.query.get_or_404(user_id)
        return render_template('user.html', user=user, pending_requests=pending_requests or [], user_role=user_role, baseurl=baseurl, issues=issues,admin=True,available=available)
    else:
        user = User.query.get_or_404(user_id)
        return render_template('user.html', user=user, user_role=user_role, baseurl=baseurl,admin=False)

@main.route('/update_profile/<int:user_id>', methods=['GET', 'POST'])
@login_required
def update_profile(user_id):
    user = User.query.get(user_id)
    if not user:
        abort(404)

    if request.method == 'POST':
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file.filename != '':
                filename = secure_filename(image_file.filename)
                upload_to_azure(image_file.stream, filename)  # Directly uploading stream
                user.image_filename = filename
                db.session.commit()
        else:
            name = request.form.get('name')
            dob_str = request.form.get('dob')
            dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            class_year = request.form.get('class_year')
            email = request.form.get('email')
            mobile_no = request.form.get('mobile_no')
            user.name = name
            user.dob = dob
            user.class_year = class_year
            user.email = email
            user.mobile_no = mobile_no
            db.session.commit()

        return redirect(url_for('main.user_profile', user_id=user.id))

    return render_template('user.html', user=user, baseurl=baseurl)



@main.route('/delete/<int:id>', methods=['GET','POST'])
def delete(id):
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.LIBRARIAN]:
        abort(403)
    book = Book.query.filter_by(id=id).first()
    if request.method == 'POST':
        if book:
            db.session.delete(book)
            db.session.commit()
            return redirect(url_for('main.librarian_dashboard'))
        abort(404) 
    return render_template('insert.html')

@main.route('/revoke/<int:id>', methods=['GET','POST'])
def revoke(id):
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.LIBRARIAN]:
        abort(403)
    book = IssueBooks.query.filter_by(id=id).first()
    user_id = current_user.id
    books = Book.query.filter_by(id=book.book_id).first()
    if request.method == 'POST':
        if book:
            db.session.delete(book)
            books.copies_available += 1
            update_book_status()
            db.session.commit()
    return redirect(request.referrer or url_for('main.user_profile', user_id=user_id))
    
@main.route('/submit_comment', methods=['POST'])
def submit_comment():
        book_id = request.form['book_id']
        comment_text = request.form['comment']
        user_id = current_user.id
        date_posted = datetime.now(IST)
        comment = Comment(book_id=book_id, text=comment_text, user_id=user_id,date_posted=date_posted)
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('main.book', id=book_id))


@main.route('/insert_book', methods=['POST'])
def insert_book():
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.LIBRARIAN]:
        abort(403)

    title = request.form['title']
    author = request.form['author']
    content = request.form['content']
    section_id = int(request.form['section_id'])
    copies_available = int(request.form['copies_available'])
    price = int(request.form['price'])

    image_file = request.files['image']
    pdf_file = request.files['pdf']

    image_filename = secure_filename(image_file.filename)
    pdf_filename = secure_filename(pdf_file.filename)

    # Upload both files to Azure
    upload_to_azure(image_file.stream, image_filename)
    upload_to_azure(pdf_file.stream, pdf_filename)

    new_book = Book(
        title=title,
        author=author,
        content=content,
        section_id=section_id,
        copies_available=copies_available,
        image_filename=image_filename,
        pdf_filename=pdf_filename,
        price=price,
        popularity=0,
        status=Status.AVAILABLE
    )
    db.session.add(new_book)
    db.session.commit()

    return redirect(url_for('main.librarian_dashboard'))


@main.route('/insert_section', methods=['POST'])
@login_required
def insert_section():
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.LIBRARIAN]:
        abort(403)
    
    section_id = int(request.form['section_id'])
    section_name = request.form['section_name']
    section_description = request.form['section_description']
    section_color = request.form['section_color']
    new_section = Section(id=section_id, name=section_name, description=section_description,color=section_color)
    
    try:
        db.session.add(new_section)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    return redirect(url_for('main.profile'))


@main.route('/cart')
@login_required
def cart():
    cart_books = current_user.cart_books
    return render_template('cart.html', cart_books=cart_books, baseurl=baseurl)

@main.route('/return_book/<int:issue_id>', methods=['DELETE'])
@login_required
def return_book(issue_id):
    issued_book = IssueBooks.query.get(issue_id)
    id = issued_book.book_id
    book = Book.query.get(id)
    if issued_book:
        db.session.delete(issued_book)
        book.copies_available += 1
        db.session.commit()
        update_book_status()
        return jsonify({'message': 'Book returned successfully'}), 200
    else:
        return jsonify({'error': 'Issued book not found'}), 404

@main.route('/remove_book/<int:cart_id>', methods=['GET','POST'])
@login_required
def remove_book(cart_id):
    cart_book = Cart.query.get(cart_id)
    if cart_book:
        db.session.delete(cart_book)
        db.session.commit()
        return redirect(url_for('main.cart'))
    else:
        return jsonify({'error': 'Issued book not found'}), 404
    
@main.route('/updatebook/<int:id>', methods=['GET', 'POST'])
def update_book(id):
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.LIBRARIAN]:
        abort(403)

    book = Book.query.get(id)
    if not book:
        abort(404)
    
    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        content = request.form['content']
        section_id = int(request.form['section_id'])
        copies_available = int(request.form['copies_available'])
        price = int(request.form['price'])

        # Retrieve and upload new files to Azure if provided
        image_file = request.files.get('image')
        pdf_file = request.files.get('pdf')

        from azure.storage.blob import BlobServiceClient
        connect_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        container_name = os.getenv('AZURE_STORAGE_CONTAINER_NAME')
        blob_service_client = BlobServiceClient.from_connection_string(connect_str)

        # Upload new image if provided
        if image_file:
            image_filename = secure_filename(image_file.filename)
            image_blob_client = blob_service_client.get_blob_client(container=container_name, blob=f'images/{image_filename}')
            image_blob_client.upload_blob(image_file, overwrite=True)
            book.image_filename = f'images/{image_filename}'

        # Upload new pdf if provided
        if pdf_file:
            pdf_filename = secure_filename(pdf_file.filename)
            pdf_blob_client = blob_service_client.get_blob_client(container=container_name, blob=f'pdfs/{pdf_filename}')
            pdf_blob_client.upload_blob(pdf_file, overwrite=True)
            book.pdf_filename = f'pdfs/{pdf_filename}'

        # Update book details in the database
        book.title = title
        book.author = author
        book.content = content
        book.section_id = section_id
        book.copies_available = copies_available
        book.price = price

        db.session.commit()
        return redirect(url_for('main.librarian_dashboard'))

    return render_template('updatebook.html', book=book, baseurl=baseurl)


@main.route('/accept_request/<int:id>', methods=['POST'])
@login_required
def accept_request(id):
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.LIBRARIAN]:
        abort(403)

    request = IssueBooks.query.get(id)
    if not request:
        abort(404)
    request.status = 'issued'
    db.session.commit()

    return redirect(url_for('main.user_profile' , user_id=request.user.id))
@main.route('/rate_book/<int:id>', methods=['POST'])
@login_required
def rate_book(id):
    stars = int(request.form.get('rate'))
    existing_rating = Rating.query.filter_by(book_id=id, user_id=current_user.id).first()
    if existing_rating:
        existing_rating.stars = stars
    else:
        new_rating = Rating(book_id=id, user_id=current_user.id, stars=stars)
        db.session.add(new_rating)
    db.session.commit()
    return jsonify({'message': 'Rating submitted successfully'}), 200

@main.route('/delete_comment/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    comment = Comment.query.get(comment_id)
    book_id = comment.book_id
    db.session.delete(comment)
    db.session.commit()

    return redirect(url_for('main.book', id=book_id))

def calculate_popularity(book):
    popularity = 0
    avg_rating = db.session.query(func.avg(Rating.stars)).filter_by(book_id=book.id).scalar()
    if avg_rating == None:
        avg_rating = 0
    if avg_rating >= 4:
        popularity += 10
    elif avg_rating == 1:
        popularity -= 10
    elif 4>avg_rating>1:
        popularity += 5
    if (datetime.utcnow() - book.uploaded_date).days < 7:
        popularity += 30
    if book.comments:
        popularity += 5 * len(book.comments)
    pop = 0
    if book.issues:
        pop += len(book.issues) * 5
    popularity += pop
    return popularity

@main.route('/checkout')
def checkout():
    user_cart_books = Cart.query.filter_by(user_id=current_user.id).all()
    book_pdf_paths = []
    for cart_book in user_cart_books:
        book = Book.query.get(cart_book.book_id)
        if book:
            book_pdf_paths.append(os.path.join('project', 'static', 'upload', book.pdf_filename))
        print(book_pdf_paths)
        zip_path = os.path.join('project', 'static', 'Assets', 'books.zip')
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for pdf_path in book_pdf_paths:
            zipf.write(pdf_path, os.path.basename(pdf_path))
    directory = 'project/static/Assets/'
    return jsonify({'downloadUrl': '/static/Assets/books.zip'})
plot_dir = os.path.join('project','static', 'Assets')
os.makedirs(plot_dir, exist_ok=True)
@main.route('/dashboard')
def dashboard():
    section_counts = db.session.query(Section.name, db.func.count(IssueHistory.book_id)).\
        join(Book, Section.id == Book.section_id).\
        join(IssueHistory, Book.id == IssueHistory.book_id).\
        group_by(Section.name).all()
    sections = [section_count[0] for section_count in section_counts]
    book_counts = [section_count[1] for section_count in section_counts]
    plt.figure(figsize=(8, 8), facecolor='#FFFBF5')
    plt.pie(book_counts, labels=sections, autopct='%1.1f%%', startangle=140)
    plt.axis('equal')
    plot_path = os.path.join(plot_dir, 'dashboard_plot.png')
    plt.savefig(plot_path)
    total_pending_books = IssueBooks.query.filter_by(status='pending').count()
    issue = IssueHistory.query.count()
    avg_rating = db.session.query(func.round(func.avg(Rating.stars), 1)).scalar()
    
    daily_counts = db.session.query(func.count('*').label('issue_count')) \
    .filter(func.date(IssueHistory.issue_date) <= datetime.now()) \
    .group_by(func.date(IssueHistory.issue_date)) \
    .subquery()
    average_issue_per_day = db.session.query(func.avg(daily_counts.c.issue_count)).scalar()
    today_issue_count = db.session.query(func.count(IssueHistory.book_id)) \
        .filter(func.date(IssueHistory.issue_date) == datetime.now().date()) \
        .scalar()
    if average_issue_per_day != 0:
        percentage = (today_issue_count / average_issue_per_day) * 100
    else:
        percentage = 0
    user_id = current_user.id
    return render_template('dashboard.html' , total_pending_books=total_pending_books, baseurl=baseurl, issue=issue, avg_rating=avg_rating,percentage=round(percentage),user_id=user_id )

@main.route('/dashboard-data')
def dashboard_data():
    all_books_issued = IssueHistory.query.order_by(IssueHistory.issue_date.asc()).all()
    all_data = [(book.issue_date.strftime('%Y-%m-%d'), 1) for book in all_books_issued]
    all_counts = {}
    for date, _ in all_data:
        all_counts[date] = all_counts.get(date, 0) + 1
    data = {
        'labels': list(all_counts.keys()),
        'all': list(all_counts.values())
    }
    return jsonify(data)

@main.route('/section')
def section():
    sec = Section.query.all()
    return render_template('section.html', sec, baseurl=baseurl)

@main.route('/delete_section/<int:section_id>', methods=['POST'])
def delete_section(section_id):
    books = Book.query.filter_by(section_id=section_id).all()
    for book in books:
        book.section_id = 0
    db.session.commit()
    section = Section.query.get_or_404(section_id)
    db.session.delete(section)
    db.session.commit()
    return redirect(url_for('main.section')) 
#flask --app project run --debug