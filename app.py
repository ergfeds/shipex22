from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import random
import string
from werkzeug.utils import secure_filename
import json

# Add this near the top of the file, after the imports
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg'}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

def get_database_url():
    if os.environ.get('RENDER'):
        # Create a data directory in the Render writable filesystem
        data_dir = '/opt/render/project/src/data'
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            print(f"Created data directory at {data_dir}")
        # Ensure proper permissions
        try:
            os.chmod(data_dir, 0o777)
            print(f"Set permissions for {data_dir}")
        except Exception as e:
            print(f"Error setting permissions for {data_dir}: {e}")
        db_path = f'{data_dir}/shipments.db'
        print(f"Using database at: {db_path}")
        return f'sqlite:///{db_path}'
    return 'sqlite:///instance/shipments.db'

# Update database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()

# Update the upload folder path for production
if os.environ.get('RENDER'):
    app.config['UPLOAD_FOLDER'] = '/opt/render/project/src/static/uploads'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Add the filter directly to Jinja environment
app.jinja_env.filters['json_loads'] = json.loads

# Create upload folder if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Add this after creating the Flask app
if not os.path.exists('instance'):
    os.makedirs('instance')

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password, method='sha256')

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

class Shipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tracking_number = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(50), nullable=False)
    
    # Sender Information
    sender_name = db.Column(db.String(100), nullable=False)
    sender_email = db.Column(db.String(120))
    sender_phone = db.Column(db.String(20))
    sender_company = db.Column(db.String(100))
    
    # Receiver Information
    receiver_name = db.Column(db.String(100), nullable=False)
    receiver_email = db.Column(db.String(120))
    receiver_phone = db.Column(db.String(20))
    receiver_company = db.Column(db.String(100))
    
    # Shipment Details
    origin = db.Column(db.String(200), nullable=False)
    destination = db.Column(db.String(200), nullable=False)
    weight = db.Column(db.Float)
    dimensions = db.Column(db.String(50))
    package_type = db.Column(db.String(50))
    
    # Service Options
    service_level = db.Column(db.String(50))
    estimated_delivery = db.Column(db.DateTime, nullable=True)
    special_instructions = db.Column(db.Text)
    
    # Tracking Details
    status_updates = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def update_status(self, new_status):
        if self.status_updates is None:
            self.status_updates = []
        
        new_update = {
            'status': new_status,
            'timestamp': datetime.utcnow().isoformat(),
            'location': self.destination if new_status in ['In Transit', 'Out for Delivery', 'Delivered', 'Customs Clearance'] else self.origin
        }
        
        self.status_updates.append(new_update)
        self.status = new_status
        
        if new_status == 'Order Registered':
            self.estimated_delivery = datetime.utcnow() + timedelta(days=7)
        elif new_status == 'Delayed':
            if self.estimated_delivery:
                self.estimated_delivery = self.estimated_delivery + timedelta(days=2)
        elif new_status == 'Delivered':
            self.estimated_delivery = datetime.utcnow()

    def to_dict(self):
        return {
            'id': self.id,
            'tracking_number': self.tracking_number,
            'sender_name': self.sender_name,
            'receiver_name': self.receiver_name,
            'origin': self.origin,
            'destination': self.destination,
            'status': self.status,
            'estimated_delivery': self.estimated_delivery.strftime('%Y-%m-%d') if self.estimated_delivery else None,
            'status_updates': self.status_updates or [],
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class PageContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(200))
    subtitle = db.Column(db.String(500))
    content = db.Column(db.Text)
    image_path = db.Column(db.String(200))
    order = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SiteSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(100), default="ShipEx")
    site_logo = db.Column(db.String(200))
    primary_color = db.Column(db.String(20), default="#522D91")
    footer_text = db.Column(db.String(500))
    contact_email = db.Column(db.String(120))
    contact_phone = db.Column(db.String(20))
    social_facebook = db.Column(db.String(200))
    social_twitter = db.Column(db.String(200))
    social_linkedin = db.Column(db.String(200))
    social_instagram = db.Column(db.String(200))
    navigation = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ContactSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='unread')  # unread, read, replied

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def home():
    return render_template('index.html', contents=get_page_contents('home'))

@app.route('/track', methods=['POST'])
def track():
    try:
        tracking_number = request.form.get('tracking_number')
        shipment = Shipment.query.filter_by(tracking_number=tracking_number).first()
        
        if shipment:
            return jsonify({
                'found': True,
                'shipment': {
                    'tracking_number': shipment.tracking_number,
                    'status': shipment.status,
                    'origin': shipment.origin,
                    'destination': shipment.destination,
                    'sender_name': shipment.sender_name,
                    'sender_email': shipment.sender_email,
                    'sender_phone': shipment.sender_phone,
                    'sender_company': shipment.sender_company,
                    'receiver_name': shipment.receiver_name,
                    'receiver_email': shipment.receiver_email,
                    'receiver_phone': shipment.receiver_phone,
                    'receiver_company': shipment.receiver_company,
                    'weight': shipment.weight,
                    'dimensions': shipment.dimensions,
                    'package_type': shipment.package_type,
                    'service_level': shipment.service_level,
                    'created_at': shipment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'updated_at': shipment.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'estimated_delivery': shipment.estimated_delivery.strftime('%Y-%m-%d') if shipment.estimated_delivery else None,
                    'status_updates': shipment.status_updates or []
                }
            })
        
        return jsonify({'found': False})
    except Exception as e:
        return jsonify({'found': False, 'error': str(e)})

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    recent_updates = PageContent.query.order_by(PageContent.updated_at.desc()).limit(5).all()
    recent_messages = ContactSubmission.query.order_by(ContactSubmission.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                         recent_updates=recent_updates,
                         recent_messages=recent_messages)

@app.route('/admin/shipments')
@login_required
def manage_shipments():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    page = request.args.get('page', 1, type=int)
    shipments = Shipment.query.order_by(Shipment.created_at.desc())\
        .paginate(page=page, per_page=20)
    
    return render_template('admin/shipments.html', shipments=shipments)

@app.route('/admin/shipment/status/<int:id>', methods=['GET', 'POST'])
@login_required
def update_status(id):
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    shipment = Shipment.query.get_or_404(id)
    
    if request.method == 'POST':
        new_status = request.form.get('status')
        if new_status:
            shipment.update_status(new_status)
            db.session.commit()
            flash('Shipment status updated successfully!', 'success')
            return redirect(url_for('manage_shipments'))
    
    return render_template('admin/update_status.html', shipment=shipment)

def generate_tracking_number():
    # Get current timestamp (last 6 digits)
    timestamp = str(int(datetime.utcnow().timestamp()))[-6:]
    # Generate 4 random uppercase letters
    letters = ''.join(random.choices(string.ascii_uppercase, k=4))
    # Generate 2 random digits
    digits = ''.join(random.choices(string.digits, k=2))
    # Combine them in a specific format
    tracking_number = f"SX{letters}{timestamp}{digits}"
    
    # Check if this tracking number already exists
    while Shipment.query.filter_by(tracking_number=tracking_number).first() is not None:
        # If it exists, generate a new one
        digits = ''.join(random.choices(string.digits, k=2))
        tracking_number = f"SX{letters}{timestamp}{digits}"
    
    return tracking_number

@app.route('/admin/shipment/new', methods=['GET', 'POST'])
@login_required
def new_shipment():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    statuses = [
        'Order Registered',
        'Package Picked Up',
        'In Transit',
        'Customs Clearance',
        'Out for Delivery',
        'Delivered',
        'On Hold',
        'Failed Delivery',
        'Return to Sender',
        'Processing',
        'Delayed'
    ]
    
    if request.method == 'POST':
        try:
            # Generate a unique tracking number
            tracking_number = generate_tracking_number()
            
            shipment = Shipment(
                tracking_number=tracking_number,  # Use generated tracking number
                status=request.form['status'],
                
                # Sender Information
                sender_name=request.form['sender_name'],
                sender_email=request.form.get('sender_email'),
                sender_phone=request.form.get('sender_phone'),
                sender_company=request.form.get('sender_company'),
                
                # Receiver Information
                receiver_name=request.form['receiver_name'],
                receiver_email=request.form.get('receiver_email'),
                receiver_phone=request.form.get('receiver_phone'),
                receiver_company=request.form.get('receiver_company'),
                
                # Shipment Details
                origin=request.form['origin'],
                destination=request.form['destination'],
                weight=float(request.form['weight']) if request.form.get('weight') else None,
                dimensions=request.form.get('dimensions'),
                package_type=request.form.get('package_type'),
                
                # Service Options
                service_level=request.form.get('service_level'),
                estimated_delivery=datetime.strptime(request.form['estimated_delivery'], '%Y-%m-%d') if request.form.get('estimated_delivery') else None,
                special_instructions=request.form.get('special_instructions'),
                
                # Initialize status updates
                status_updates=[{
                    'status': request.form['status'],
                    'timestamp': datetime.utcnow().isoformat(),
                    'location': request.form['origin']
                }]
            )
            
            db.session.add(shipment)
            db.session.commit()
            flash(f'Shipment created successfully! Tracking number: {tracking_number}', 'success')
            return redirect(url_for('admin'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating shipment: {str(e)}', 'danger')
    
    return render_template('admin/new_shipment.html', statuses=statuses)

@app.route('/admin/shipment/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_shipment(id):
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    statuses = [
        'Order Registered',
        'Package Picked Up',
        'In Transit',
        'Customs Clearance',
        'Out for Delivery',
        'Delivered',
        'On Hold',
        'Failed Delivery',
        'Return to Sender',
        'Processing',
        'Delayed'
    ]
    
    shipment = Shipment.query.get_or_404(id)
    if request.method == 'POST':
        old_status = shipment.status
        new_status = request.form['status']
        
        shipment.tracking_number = request.form['tracking_number']
        shipment.sender_name = request.form['sender_name']
        shipment.receiver_name = request.form['receiver_name']
        shipment.origin = request.form['origin']
        shipment.destination = request.form['destination']
        
        if old_status != new_status:
            shipment.update_status(new_status)
        
        try:
            db.session.commit()
            flash('Shipment updated successfully!', 'success')
            return redirect(url_for('admin'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating shipment: {str(e)}', 'danger')
    
    return render_template('admin/edit_shipment.html', shipment=shipment, statuses=statuses)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        print(f"Login attempt with username: {username}")
        
        user = User.query.filter_by(username=username).first()
        if user:
            print("User found in database")
            if user.verify_password(password):
                print("Password verified successfully")
                login_user(user)
                flash('Logged in successfully!', 'success')
                return redirect(url_for('admin'))
            else:
                print("Password verification failed")
        else:
            print("User not found in database")
            
        flash('Invalid username or password', 'danger')
    return render_template('admin/login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/check_admin')
def check_admin():
    admin = User.query.filter_by(username='admin').first()
    if admin:
        return f"Admin exists with ID: {admin.id}"
    return "No admin user found"

@app.route('/admin/shipment/<int:id>/delete', methods=['DELETE'])
@login_required
def delete_shipment(id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        shipment = Shipment.query.get_or_404(id)
        db.session.delete(shipment)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

def init_db():
    with app.app_context():
        # Don't drop tables by default
        print("Checking database tables...")
        db.create_all()  # This will only create tables that don't exist
        
        # Check if admin user exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("Creating new admin user...")
            admin = User(
                username='admin',
                password='admin123',  # This will be hashed by the setter
                is_admin=True
            )
            db.session.add(admin)
            try:
                db.session.commit()
                print("Admin user created successfully!")
                # Verify the admin was created
                admin_check = User.query.filter_by(username='admin').first()
                if admin_check and admin_check.verify_password('admin123'):
                    print("Admin user verified successfully!")
                else:
                    print("Warning: Admin user verification failed!")
            except Exception as e:
                print(f"Error creating admin user: {e}")
                db.session.rollback()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/admin/content')
@login_required
def manage_content():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    contents = PageContent.query.order_by(PageContent.section, PageContent.order).all()
    return render_template('admin/manage_content.html', contents=contents)

@app.route('/admin/content/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_content(id):
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    content = PageContent.query.get_or_404(id)
    
    if request.method == 'POST':
        content.title = request.form.get('title')
        content.subtitle = request.form.get('subtitle')
        content.order = request.form.get('order', type=int)
        
        # Add this section for handling footer content
        if content.section == 'footer':
            footer_data = {
                'company_description': request.form.get('company_description'),
                'quick_links': [
                    {
                        'title': request.form.get(f'quick_link_title_{i}'),
                        'url': request.form.get(f'quick_link_url_{i}')
                    }
                    for i in range(1, 5)  # Assuming 4 quick links
                ],
                'services': [
                    {
                        'title': request.form.get(f'service_title_{i}'),
                        'url': request.form.get(f'service_url_{i}')
                    }
                    for i in range(1, 5)  # Assuming 4 services
                ],
                'contact_info': {
                    'phone': request.form.get('contact_phone'),
                    'email': request.form.get('contact_email'),
                    'address': request.form.get('contact_address')
                },
                'copyright': request.form.get('copyright'),
                'legal_links': [
                    {
                        'title': request.form.get(f'legal_link_title_{i}'),
                        'url': request.form.get(f'legal_link_url_{i}')
                    }
                    for i in range(1, 4)  # Assuming 3 legal links
                ]
            }
            content.content = json.dumps(footer_data)

        # Handle section-specific image uploads
        if content.section == 'hero':
            if 'hero_image' in request.files:
                file = request.files['hero_image']
                if file and allowed_file(file.filename):
                    try:
                        # Create a secure filename with timestamp to prevent caching
                        filename = secure_filename(f"hero_{int(datetime.utcnow().timestamp())}_{file.filename}")
                        
                        # Ensure upload directory exists
                        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                        
                        # Create the full path
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        
                        # Save the file
                        file.save(file_path)
                        
                        # Update the database with the relative path
                        content.image_path = f'uploads/{filename}'
                        
                        # Log success
                        print(f"Hero image saved: {content.image_path}")
                    except Exception as e:
                        print(f"Error saving hero image: {str(e)}")
                        flash(f'Error saving file: {str(e)}', 'error')
                        return redirect(request.url)
        
        elif content.section == 'services':
            services_data = json.loads(content.content)
            for idx, service in enumerate(services_data, 1):
                file_key = f'service_icon_{idx}'
                if file_key in request.files:
                    file = request.files[file_key]
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        try:
                            file.save(file_path)
                            service['icon_path'] = f'uploads/{filename}'
                        except Exception as e:
                            flash(f'Error saving file: {str(e)}', 'error')
                            return redirect(request.url)
            content.content = json.dumps(services_data)

        elif content.section == 'testimonials':
            testimonials_data = json.loads(content.content)
            for idx, testimonial in enumerate(testimonials_data, 1):
                file_key = f'testimonial_image_{idx}'
                if file_key in request.files:
                    file = request.files[file_key]
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        testimonial['image_path'] = f'uploads/{filename}'
            content.content = json.dumps(testimonials_data)

        elif content.section == 'why_choose_us':
            benefits_data = json.loads(content.content)
            for idx, benefit in enumerate(benefits_data, 1):
                file_key = f'benefit_icon_{idx}'
                if file_key in request.files:
                    file = request.files[file_key]
                    if file and allowed_file(file.filename):
                        try:
                            # Create a secure filename with timestamp
                            filename = secure_filename(f"benefit_{int(datetime.utcnow().timestamp())}_{file.filename}")
                            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                            file.save(file_path)
                            benefit['icon_path'] = f'uploads/{filename}'
                            print(f"Benefit icon saved: {benefit['icon_path']}")
                        except Exception as e:
                            print(f"Error saving benefit icon: {str(e)}")
                            flash(f'Error saving file: {str(e)}', 'error')
                            return redirect(request.url)
            content.content = json.dumps(benefits_data)

        elif content.section == 'statistics':
            stats_data = json.loads(content.content)
            for idx, stat in enumerate(stats_data, 1):
                file_key = f'stat_icon_{idx}'
                if file_key in request.files:
                    file = request.files[file_key]
                    if file and allowed_file(file.filename):
                        try:
                            filename = secure_filename(f"stat_{int(datetime.utcnow().timestamp())}_{file.filename}")
                            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                            file.save(file_path)
                            stat['icon_path'] = f'uploads/{filename}'
                            print(f"Stat icon saved: {stat['icon_path']}")
                        except Exception as e:
                            print(f"Error saving stat icon: {str(e)}")
                            flash(f'Error saving file: {str(e)}', 'error')
                            return redirect(request.url)
            content.content = json.dumps(stats_data)

        # Add other section-specific handling as needed
        
        try:
            db.session.commit()
            flash('Content updated successfully!', 'success')
            return redirect(url_for('manage_content'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating content: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('admin/edit_content.html', content=content)

@app.route('/admin/content/new', methods=['GET', 'POST'])
@login_required
def new_content():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        content = PageContent(
            section=request.form.get('section'),
            title=request.form.get('title'),
            subtitle=request.form.get('subtitle'),
            content=request.form.get('content'),
            order=request.form.get('order', type=int)
        )
        
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                content.image_path = f'uploads/{filename}'
        
        db.session.add(content)
        db.session.commit()
        flash('New content added successfully!', 'success')
        return redirect(url_for('manage_content'))
    
    return render_template('admin/new_content.html')

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def manage_settings():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    settings = SiteSettings.query.first()
    if not settings:
        settings = SiteSettings()
        db.session.add(settings)
        db.session.commit()
    
    if request.method == 'POST':
        settings.site_name = request.form.get('site_name')
        settings.primary_color = request.form.get('primary_color')
        settings.footer_text = request.form.get('footer_text')
        settings.contact_email = request.form.get('contact_email')
        settings.contact_phone = request.form.get('contact_phone')
        settings.social_facebook = request.form.get('social_facebook')
        settings.social_twitter = request.form.get('social_twitter')
        settings.social_linkedin = request.form.get('social_linkedin')
        settings.social_instagram = request.form.get('social_instagram')
        
        if 'site_logo' in request.files:
            file = request.files['site_logo']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                settings.site_logo = f'uploads/{filename}'
        
        db.session.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('manage_settings'))
    
    return render_template('admin/settings.html', settings=settings)

@app.route('/admin/initialize-content')
@login_required
def initialize_content():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    # Define the default sections
    default_sections = [
        {
            'section': 'hero',
            'title': 'Welcome to ShipEx',
            'subtitle': 'Your trusted partner in global shipping and logistics',
            'content': 'Track your shipment or get started with a new delivery.',
            'image_path': '',  # Hero background image
            'order': 1
        },
        {
            'section': 'services_page',
            'title': 'Our Services',
            'subtitle': 'Comprehensive shipping solutions for all your needs',
            'content': json.dumps([
                {
                    'title': 'Global Shipping',
                    'description': 'Ship your packages worldwide with reliable tracking and fast delivery.',
                    'features': [
                        'Door-to-door delivery',
                        'Real-time tracking',
                        'Customs clearance',
                        'Insurance coverage'
                    ],
                    'icon_path': '',
                    'link': '/services/global-shipping'
                },
                {
                    'title': 'Express Delivery',
                    'description': 'Fast and reliable delivery for urgent shipments.',
                    'features': [
                        'Same-day delivery',
                        'Next-day delivery',
                        'Priority handling',
                        'Time-specific delivery'
                    ],
                    'icon_path': '',
                    'link': '/services/express-delivery'
                },
                {
                    'title': 'Freight Services',
                    'description': 'Comprehensive freight solutions for businesses.',
                    'features': [
                        'Air freight',
                        'Ocean freight',
                        'Road freight',
                        'Multimodal solutions'
                    ],
                    'icon_path': '',
                    'link': '/services/freight'
                }
            ]),
            'image_path': '',
            'order': 2
        },
        {
            'section': 'how_it_works',
            'title': 'How ShipEx Works',
            'subtitle': 'Simple steps to ship your package',
            'content': json.dumps([
                {
                    'step': 1,
                    'title': 'Book',
                    'description': 'Enter your shipping details and book your delivery.',
                    'icon_path': ''
                },
                {
                    'step': 2,
                    'title': 'Pack',
                    'description': 'Package your items securely using our guidelines.',
                    'icon_path': ''
                },
                {
                    'step': 3,
                    'title': 'Ship',
                    'description': 'We pick up your package and start the delivery.',
                    'icon_path': ''
                },
                {
                    'step': 4,
                    'title': 'Track',
                    'description': 'Monitor your shipment with real-time tracking.',
                    'icon_path': ''
                }
            ]),
            'image_path': '',
            'order': 3
        },
        {
            'section': 'testimonials',
            'title': 'What Our Customers Say',
            'subtitle': 'Trusted by thousands of satisfied customers',
            'content': json.dumps([
                {
                    'text': 'Excellent service! My package arrived ahead of schedule and in perfect condition.',
                    'author': 'Sarah Johnson',
                    'image_path': ''
                },
                {
                    'text': 'The tracking system is amazing. I knew exactly where my package was at all times.',
                    'author': 'Michael Chen',
                    'image_path': ''
                },
                {
                    'text': 'Best shipping service I\'ve used. Their customer support is outstanding!',
                    'author': 'Emma Davis',
                    'image_path': ''
                }
            ]),
            'image_path': '',
            'order': 4
        },
        {
            'section': 'why_choose_us',
            'title': 'Why Choose ShipEx',
            'subtitle': 'Experience the difference with our premium shipping services',
            'content': json.dumps([
                {
                    'title': 'Global Network',
                    'description': 'Access to worldwide shipping routes and partners for seamless delivery.',
                    'icon_path': ''
                },
                {
                    'title': 'Real-time Tracking',
                    'description': 'Track your shipments 24/7 with precise location updates.',
                    'icon_path': ''
                },
                {
                    'title': '24/7 Support',
                    'description': 'Round-the-clock customer service to assist you anytime.',
                    'icon_path': ''
                },
                {
                    'title': 'Secure Shipping',
                    'description': 'Advanced security measures to protect your valuable packages.',
                    'icon_path': ''
                }
            ]),
            'image_path': '',
            'order': 5
        },
        {
            'section': 'app_download',
            'title': 'Mobile App Coming Soon',
            'subtitle': 'Experience the future of shipping with our upcoming mobile app',
            'content': json.dumps({
                'features': [
                    'Real-time shipment tracking',
                    'Instant notifications and updates',
                    'Easy booking and management',
                    'Secure digital documentation',
                    'Quick customer support access'
                ]
            }),
            'image_path': '',  # Empty image path
            'order': 6
        },
        {
            'section': 'statistics',
            'title': 'Our Global Reach',
            'subtitle': 'Numbers that speak for themselves',
            'content': json.dumps([
                {
                    'number': '200+',
                    'label': 'Countries Served',
                    'icon_path': ''
                },
                {
                    'number': '1M+',
                    'label': 'Happy Customers',
                    'icon_path': ''
                },
                {
                    'number': '5M+',
                    'label': 'Packages Delivered',
                    'icon_path': ''
                },
                {
                    'number': '50+',
                    'label': 'Global Offices',
                    'icon_path': ''
                }
            ]),
            'image_path': '',
            'order': 4  # Adjust order as needed
        },
        {
            'section': 'footer',
            'title': 'Footer',
            'subtitle': 'Footer Information',
            'content': json.dumps({
                'company_description': 'Your trusted partner in global shipping and logistics. Delivering excellence worldwide.',
                'quick_links': [
                    {'title': 'Track Shipment', 'url': '#'},
                    {'title': 'Get a Quote', 'url': '#'},
                    {'title': 'Locations', 'url': '#'},
                    {'title': 'Services', 'url': '#'}
                ],
                'services': [
                    {'title': 'Global Shipping', 'url': '#'},
                    {'title': 'Express Delivery', 'url': '#'},
                    {'title': 'Cargo Shipping', 'url': '#'},
                    {'title': 'E-commerce Solutions', 'url': '#'}
                ],
                'contact_info': {
                    'phone': '+1 (555) 123-4567',
                    'email': 'support@shipex.com',
                    'address': '123 Shipping Lane\nLogistics City, LC 12345'
                },
                'copyright': '© 2024 ShipEx. All rights reserved.',
                'legal_links': [
                    {'title': 'Privacy Policy', 'url': '#'},
                    {'title': 'Terms of Service', 'url': '#'},
                    {'title': 'Cookie Policy', 'url': '#'}
                ]
            }),
            'image_path': '',
            'order': 7
        },
        {
            'section': 'about_page',
            'title': 'Your Trusted Shipping Partner',
            'subtitle': 'Learn about our mission and values',
            'content': json.dumps({
                'main_text': 'ShipEx has been a leader in global shipping and logistics for over two decades.',
                'values': [
                    {
                        'title': 'Reliability',
                        'description': 'We deliver on our promises.',
                        'icon': 'fa-shield-alt'
                    },
                    {
                        'title': 'Innovation',
                        'description': 'Continuously improving our services.',
                        'icon': 'fa-lightbulb'
                    },
                    {
                        'title': 'Sustainability',
                        'description': 'Committed to environmental responsibility.',
                        'icon': 'fa-leaf'
                    },
                    {
                        'title': 'Customer Focus',
                        'description': 'Your satisfaction is our priority.',
                        'icon': 'fa-heart'
                    }
                ]
            }),
            'image_path': '',
            'order': 1
        }
    ]
    
    # Add sections to database if they don't exist
    for section_data in default_sections:
        existing_section = PageContent.query.filter_by(
            section=section_data['section']
        ).first()
        
        if not existing_section:
            new_section = PageContent(
                section=section_data['section'],
                title=section_data['title'],
                subtitle=section_data['subtitle'],
                content=section_data['content'],
                image_path=section_data['image_path'],
                order=section_data['order']
            )
            db.session.add(new_section)
    
    try:
        db.session.commit()
        flash('Homepage content initialized successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error initializing content: {str(e)}', 'error')
    
    return redirect(url_for('manage_content'))

@app.route('/debug/why-choose-us')
def debug_why_choose_us():
    content = PageContent.query.filter_by(section='why_choose_us').first()
    if content:
        try:
            parsed_content = json.loads(content.content)
            return {
                'title': content.title,
                'subtitle': content.subtitle,
                'content': parsed_content,
                'raw_content': content.content
            }
        except Exception as e:
            return {'error': str(e), 'raw_content': content.content}
    return {'error': 'Section not found'}

@app.route('/admin/navigation', methods=['GET', 'POST'])
@login_required
def manage_navigation():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    settings = SiteSettings.query.first()
    if not settings:
        settings = SiteSettings()
        db.session.add(settings)
        db.session.commit()
    
    if request.method == 'POST':
        try:
            nav_items = []
            for i in range(10):
                title = request.form.get(f'nav_title_{i}')
                url = request.form.get(f'nav_url_{i}')
                if title and url:
                    # Ensure proper URL formatting
                    if url != '/' and url.endswith('/'):
                        url = url.rstrip('/')
                    if not url.startswith('/') and not url.startswith('#'):
                        url = '/' + url
                    nav_items.append({'title': title, 'url': url})
            
            settings.navigation = json.dumps(nav_items)
            db.session.commit()
            db.session.refresh(settings)
            
            flash('Navigation menu updated successfully!', 'success')
            return redirect(url_for('manage_navigation', _t=datetime.utcnow().timestamp()))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating navigation: {str(e)}', 'error')
            return redirect(url_for('manage_navigation'))
    
    current_nav = [
        {'title': 'Home', 'url': '/'},
        {'title': 'Services', 'url': '/services'},
        {'title': 'Track', 'url': '#tracking'},
        {'title': 'About', 'url': '/about'},
        {'title': 'Contact', 'url': '/contact'}
    ] if not settings.navigation else json.loads(settings.navigation)
    
    return render_template('admin/navigation.html', nav_items=current_nav)

@app.route('/admin/footer', methods=['GET', 'POST'])
@login_required
def manage_footer():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        try:
            footer_content = {
                'company_description': request.form.get('company_description'),
                'contact_info': {
                    'phone': request.form.get('contact_phone'),
                    'email': request.form.get('contact_email'),
                    'address': request.form.get('contact_address')
                },
                'quick_links': [],
                'legal_links': []
            }
            
            # Process quick links
            for i in range(5):
                title = request.form.get(f'quick_link_title_{i}')
                url = request.form.get(f'quick_link_url_{i}')
                if title and url:
                    footer_content['quick_links'].append({'title': title, 'url': url})
            
            # Process legal links
            for i in range(5):
                title = request.form.get(f'legal_link_title_{i}')
                url = request.form.get(f'legal_link_url_{i}')
                if title and url:
                    footer_content['legal_links'].append({'title': title, 'url': url})
            
            # Update footer content
            footer_section = PageContent.query.filter_by(section='footer').first()
            if footer_section:
                footer_section.content = json.dumps(footer_content)
                db.session.commit()
                flash('Footer content updated successfully!', 'success')
            else:
                flash('Footer section not found!', 'error')
                
        except Exception as e:
            flash(f'Error updating footer: {str(e)}', 'error')
        
        return redirect(url_for('manage_footer'))
    
    # Get current footer content
    footer_section = PageContent.query.filter_by(section='footer').first()
    footer_content = {}
    if footer_section:
        try:
            footer_content = json.loads(footer_section.content)
        except:
            footer_content = {}
    
    return render_template('admin/footer.html', footer_content=footer_content)

@app.route('/services')
def services():
    return render_template('services.html', contents=get_page_contents('services'))

@app.route('/about')
def about():
    # Get page contents
    contents = PageContent.query.order_by(PageContent.order).all()
    content_dict = {}
    
    # Process all content sections
    for content in contents:
        content_dict[content.section] = {
            'title': content.title,
            'subtitle': content.subtitle,
            'image_path': content.image_path,
            'order': content.order
        }
        try:
            if content.content:
                content_dict[content.section]['content'] = json.loads(content.content)
        except json.JSONDecodeError:
            content_dict[content.section]['content'] = {
                'main_text': content.content,
                'values': []
            }
    
    # Initialize about page content if it doesn't exist
    if 'about_page' not in content_dict:
        content_dict['about_page'] = {
            'title': 'Your Trusted Shipping Partner',
            'subtitle': 'Learn about our mission and values',
            'content': {
                'main_text': 'ShipEx has been a leader in global shipping and logistics for over two decades.',
                'values': [
                    {
                        'title': 'Reliability',
                        'description': 'We deliver on our promises.',
                        'icon': 'fa-shield-alt'
                    },
                    {
                        'title': 'Innovation',
                        'description': 'Continuously improving our services.',
                        'icon': 'fa-lightbulb'
                    },
                    {
                        'title': 'Sustainability',
                        'description': 'Committed to environmental responsibility.',
                        'icon': 'fa-leaf'
                    },
                    {
                        'title': 'Customer Focus',
                        'description': 'Your satisfaction is our priority.',
                        'icon': 'fa-heart'
                    }
                ]
            }
        }
    
    return render_template('about.html', contents=content_dict)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        submission = ContactSubmission(
            name=request.form.get('name'),
            email=request.form.get('email'),
            subject=request.form.get('subject'),
            message=request.form.get('message')
        )
        db.session.add(submission)
        db.session.commit()
        
        flash('Thank you for your message. We will get back to you soon!', 'success')
        return redirect(url_for('contact'))
        
    return render_template('contact.html', contents=get_page_contents('contact'))

def get_page_contents(page_section):
    contents = PageContent.query.order_by(PageContent.order).all()
    content_dict = {}
    for content in contents:
        content_dict[content.section] = {
            'title': content.title,
            'subtitle': content.subtitle,
            'content': content.content,
            'image_path': content.image_path,
            'order': content.order
        }
        try:
            if content.content:
                content_dict[content.section]['content'] = json.loads(content.content)
        except:
            pass
    return content_dict

@app.template_filter('from_json')
def from_json(value):
    try:
        return json.loads(value)
    except:
        return []

@app.context_processor
def inject_settings():
    settings = SiteSettings.query.first()
    if settings:
        db.session.refresh(settings)
    return {'settings': settings}

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

@app.route('/admin/messages')
@login_required
def manage_messages():
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    page = request.args.get('page', 1, type=int)
    messages = ContactSubmission.query.order_by(ContactSubmission.created_at.desc())\
        .paginate(page=page, per_page=10)
    
    return render_template('admin/messages.html', messages=messages)

@app.route('/admin/messages/<int:id>/status', methods=['POST'])
@login_required
def update_message_status(id):
    if not current_user.is_admin:
        return redirect(url_for('home'))
    
    message = ContactSubmission.query.get_or_404(id)
    message.status = request.form.get('status', 'read')
    db.session.commit()
    
    return jsonify({'status': 'success'})

def create_tables():
    with app.app_context():
        try:
            # Get database path - extract from SQLAlchemy URI
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            db_exists = os.path.exists(db_path)
            
            print(f"Database path: {db_path}")
            print(f"Database exists: {db_exists}")
            
            # Always create tables if they don't exist
            db.create_all()
            
            # Only create admin user if the database is new
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                print("Creating admin user...")
                admin = User(
                    username='admin',
                    password='admin123',
                    is_admin=True
                )
                db.session.add(admin)
                db.session.commit()
                print("Admin user created successfully!")
            else:
                print("Admin user already exists.")
        except Exception as e:
            print(f"Error during database initialization: {e}")
            db.session.rollback()

# Add after creating the Flask app
@app.errorhandler(500)
def internal_error(error):
    print(f"Server Error: {error}")
    return "Internal Server Error", 500

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"Unhandled Exception: {e}")
    return "Internal Server Error", 500

# After creating the Flask app
required_dirs = [
    'instance',
    'static/uploads',
    '/opt/render/project/src/data',
    '/opt/render/project/src/static/uploads'
]

for directory in required_dirs:
    if not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"Created directory: {directory}")
        except Exception as e:
            print(f"Error creating directory {directory}: {e}")

@app.route('/health', methods=['GET'])
def health_check():
    health_data = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "render": bool(os.environ.get('RENDER')),
        "database": "unknown"
    }
    
    # Check database connection
    try:
        # Simple query to test database connection
        db_check = db.session.execute('SELECT 1').fetchone()
        if db_check:
            health_data["database"] = "connected"
            # Check if admin user exists
            admin = User.query.filter_by(username='admin').first()
            health_data["admin_exists"] = bool(admin)
        else:
            health_data["database"] = "error"
    except Exception as e:
        health_data["status"] = "degraded"
        health_data["database"] = "error"
        health_data["error"] = str(e)
    
    # Check file system
    try:
        data_dir = '/opt/render/project/src/data' if os.environ.get('RENDER') else 'instance'
        health_data["data_dir_exists"] = os.path.exists(data_dir)
        
        if os.environ.get('RENDER'):
            db_file = f"{data_dir}/shipments.db"
            health_data["db_file_exists"] = os.path.exists(db_file)
            if os.path.exists(db_file):
                health_data["db_file_size"] = os.path.getsize(db_file)
    except Exception as e:
        health_data["filesystem_error"] = str(e)
    
    return jsonify(health_data), 200

if __name__ == '__main__':
    create_tables()
    app.run(host='0.0.0.0')
else:
    # This ensures tables are created when running under gunicorn
    create_tables()
