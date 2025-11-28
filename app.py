import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_cors import CORS
from models import db, User, About, Skill, Education, Experience, Project, Thesis, ContactMessage

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'

# --- DATABASE CONFIGURATION ---
# NOTE: Ensure this connection string is correct for your environment. 
# If testing locally without internet, you might want to use sqlite: 'sqlite:///portfolio.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://neondb_owner:npg_hPOHG15SvjBZ@ep-morning-art-a1mg0i01-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- FIX FOR SSL CONNECTION CLOSED ERROR ---
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

# Configure Uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directories exist
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'projects'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'thesis'), exist_ok=True)

CORS(app)

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- SETUP / INIT ---
@app.cli.command("create-admin")
def create_admin():
    """Creates tables and an admin user."""
    with app.app_context():
        try:
            db.create_all()
            if not User.query.filter_by(username='admin').first():
                hashed_pw = generate_password_hash('admin123', method='pbkdf2:sha256')
                new_user = User(username='admin', password=hashed_pw)
                db.session.add(new_user)
                # Create default 'About' entry if it doesn't exist
                if not About.query.first():
                    db.session.add(About(name="Your Name"))
                db.session.commit()
                print("Admin created (user: admin, pass: admin123)")
            else:
                print("Admin already exists")
        except Exception as e:
            print(f"Error connecting to Database: {e}")

# --- PUBLIC ROUTE (THE PORTFOLIO) ---
@app.route('/')
def index():
    """
    Serves the main portfolio website.
    The frontend JS will fetch data from the /api/ endpoints.
    """
    # We use make_response to attach headers that prevent the browser from 
    # caching a redirect if one existed previously.
    response = make_response(render_template('index.html'))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# --- AUTH ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Helper: If user is already logged in, send them to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ADMIN DASHBOARD ROUTES ---
@app.route('/admin')      # CHANGED: Now accessible at /admin
@app.route('/dashboard')  # CHANGED: Now accessible at /dashboard
@login_required
def dashboard():
    active_tab = request.args.get('tab', 'messages')
    
    about = About.query.first()
    skills = Skill.query.all()
    education = Education.query.all()
    experience = Experience.query.all()
    projects = Project.query.all()
    theses = Thesis.query.all()
    
    # Sort messages by date descending (newest first)
    messages = ContactMessage.query.order_by(ContactMessage.timestamp.desc()).all()
    
    # Count unread messages
    unread_count = ContactMessage.query.filter_by(read=False).count()
    
    return render_template('dashboard.html', 
                           about=about, skills=skills, education=education, 
                           experience=experience, projects=projects, 
                           theses=theses, messages=messages,
                           unread_count=unread_count,
                           active_tab=active_tab)

# --- MESSAGE ROUTES ---

@app.route('/api/message/read/<int:id>', methods=['POST'])
@login_required
def mark_message_read(id):
    msg = ContactMessage.query.get_or_404(id)
    if not msg.read:
        msg.read = True
        db.session.commit()
    
    # Return new unread count
    new_count = ContactMessage.query.filter_by(read=False).count()
    return jsonify({'success': True, 'unread_count': new_count})


# --- CRUD ROUTES (Backend Operations) ---

@app.route('/update/about', methods=['POST'])
@login_required
def update_about():
    about = About.query.first()
    if not about:
        about = About()
        db.session.add(about)
    
    about.name = request.form.get('name')
    about.birthday = request.form.get('birthday')
    about.website = request.form.get('website')
    about.phone = request.form.get('phone')
    about.city = request.form.get('city')
    about.age = request.form.get('age')
    about.degree = request.form.get('degree')
    about.email = request.form.get('email')
    about.freelance_status = request.form.get('freelance_status')
    about.short_bio = request.form.get('short_bio')
    about.long_bio = request.form.get('long_bio')
    about.profile_image = request.form.get('profile_image')
    
    db.session.commit()
    flash('About section updated!')
    return redirect(url_for('dashboard', tab='about'))

@app.route('/add/skill', methods=['POST'])
@login_required
def add_skill():
    new_skill = Skill(name=request.form['name'], percentage=request.form['percentage'])
    db.session.add(new_skill)
    db.session.commit()
    return redirect(url_for('dashboard', tab='skills'))

@app.route('/delete/skill/<int:id>')
@login_required
def delete_skill(id):
    Skill.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect(url_for('dashboard', tab='skills'))

@app.route('/edit/skill/<int:id>', methods=['POST'])
@login_required
def edit_skill(id):
    skill = Skill.query.get_or_404(id)
    skill.name = request.form['name']
    skill.percentage = request.form['percentage']
    db.session.commit()
    flash('Skill updated successfully!')
    return redirect(url_for('dashboard', tab='skills'))

@app.route('/add/education', methods=['POST'])
@login_required
def add_education():
    new_edu = Education(
        degree=request.form['degree'],
        institution=request.form['institution'],
        year_range=request.form['year_range'],
        description=request.form['description']
    )
    db.session.add(new_edu)
    db.session.commit()
    return redirect(url_for('dashboard', tab='education'))

@app.route('/delete/education/<int:id>')
@login_required
def delete_education(id):
    Education.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect(url_for('dashboard', tab='education'))

@app.route('/edit/education/<int:id>', methods=['POST'])
@login_required
def edit_education(id):
    edu = Education.query.get_or_404(id)
    edu.degree = request.form['degree']
    edu.institution = request.form['institution']
    edu.year_range = request.form['year_range']
    edu.description = request.form['description']
    db.session.commit()
    flash('Education updated successfully!')
    return redirect(url_for('dashboard', tab='education'))

@app.route('/add/experience', methods=['POST'])
@login_required
def add_experience():
    new_exp = Experience(
        role=request.form['role'],
        company=request.form['company'],
        year_range=request.form['year_range'],
        description=request.form['description']
    )
    db.session.add(new_exp)
    db.session.commit()
    return redirect(url_for('dashboard', tab='experience'))

@app.route('/delete/experience/<int:id>')
@login_required
def delete_experience(id):
    Experience.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect(url_for('dashboard', tab='experience'))

@app.route('/edit/experience/<int:id>', methods=['POST'])
@login_required
def edit_experience(id):
    exp = Experience.query.get_or_404(id)
    exp.role = request.form['role']
    exp.company = request.form['company']
    exp.year_range = request.form['year_range']
    exp.description = request.form['description']
    db.session.commit()
    flash('Experience updated successfully!')
    return redirect(url_for('dashboard', tab='experience'))

@app.route('/add/project', methods=['POST'])
@login_required
def add_project():
    image_url = request.form.get('image_url')
    
    if 'image_file' in request.files:
        file = request.files['image_file']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'projects', filename)
            file.save(filepath)
            # Ensure URL uses forward slashes
            image_url = '/' + filepath.replace('\\', '/')

    new_proj = Project(
        title=request.form['title'],
        category=request.form['category'],
        image_url=image_url,
        project_link=request.form['project_link']
    )
    db.session.add(new_proj)
    db.session.commit()
    return redirect(url_for('dashboard', tab='projects'))

@app.route('/delete/project/<int:id>')
@login_required
def delete_project(id):
    Project.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect(url_for('dashboard', tab='projects'))

@app.route('/edit/project/<int:id>', methods=['POST'])
@login_required
def edit_project(id):
    proj = Project.query.get_or_404(id)
    proj.title = request.form['title']
    proj.category = request.form['category']
    proj.project_link = request.form['project_link']
    proj.image_url = request.form['image_url']
    db.session.commit()
    flash('Project updated successfully!')
    return redirect(url_for('dashboard', tab='projects'))

@app.route('/add/thesis', methods=['POST'])
@login_required
def add_thesis():
    link = request.form.get('link')

    if 'thesis_pdf' in request.files:
        file = request.files['thesis_pdf']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'thesis', filename)
            file.save(filepath)
            link = '/' + filepath.replace('\\', '/')

    new_thesis = Thesis(
        title=request.form['title'],
        description=request.form['description'],
        link=link,
        publication_date=request.form['publication_date']
    )
    db.session.add(new_thesis)
    db.session.commit()
    return redirect(url_for('dashboard', tab='thesis'))

@app.route('/delete/thesis/<int:id>')
@login_required
def delete_thesis(id):
    Thesis.query.filter_by(id=id).delete()
    db.session.commit()
    return redirect(url_for('dashboard', tab='thesis'))

@app.route('/edit/thesis/<int:id>', methods=['POST'])
@login_required
def edit_thesis(id):
    thesis = Thesis.query.get_or_404(id)
    thesis.title = request.form['title']
    thesis.publication_date = request.form['publication_date']
    thesis.link = request.form['link']
    thesis.description = request.form['description']
    db.session.commit()
    flash('Thesis updated successfully!')
    return redirect(url_for('dashboard', tab='thesis'))

# --- PUBLIC API (Fetching Data for Portfolio) ---

@app.route('/api/about', methods=['GET'])
def get_about():
    about = About.query.first()
    return jsonify(about.to_dict() if about else {})

@app.route('/api/skills', methods=['GET'])
def get_skills():
    skills = Skill.query.all()
    return jsonify([s.to_dict() for s in skills])

@app.route('/api/education', methods=['GET'])
def get_education():
    education = Education.query.all()
    return jsonify([e.to_dict() for e in education])

@app.route('/api/experience', methods=['GET'])
def get_experience():
    experience = Experience.query.all()
    return jsonify([e.to_dict() for e in experience])

@app.route('/api/projects', methods=['GET'])
def get_projects():
    projects = Project.query.all()
    return jsonify([p.to_dict() for p in projects])

@app.route('/api/thesis', methods=['GET'])
def get_thesis():
    thesis = Thesis.query.all()
    return jsonify([t.to_dict() for t in thesis])

@app.route('/api/contact', methods=['POST'])
def api_contact():
    data = request.json or request.form
    if not data:
        return jsonify({"error": "No data provided"}), 400

    new_msg = ContactMessage(
        name=data.get('name'),
        email=data.get('email'),
        subject=data.get('subject'),
        message=data.get('message')
    )
    db.session.add(new_msg)
    db.session.commit()
    return jsonify({"success": True, "message": "Message sent successfully!"}), 201

if __name__ == '__main__':
    app.run(debug=True)