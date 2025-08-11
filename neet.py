# neet.py
from flask import Blueprint, render_template
from flask_login import login_required

neet = Blueprint('neet', __name__)

@neet.route('/neet')
@login_required
def portal_home():
    """Renders the main NEET Portal landing page."""
    return render_template('neet_home.html')

@neet.route('/neet/physics/projectile-motion')
@login_required
def projectile_motion():
    """Renders the Projectile Motion simulator page."""
    # Note: We are now rendering the file renamed to 'projectile_motion_simulator.html'
    return render_template('projectile_motion_simulator.html')