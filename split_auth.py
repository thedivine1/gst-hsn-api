import os

with open("dashboard.html", "r", encoding="utf-8") as f:
    dash_html = f.read()

# dashboard.html has the full structure, we'll create login.html from it by removing dashboard parts
login_html = dash_html.replace("<title>Developer Dashboard — GST Accelerator</title>", "<title>Login — GST Accelerator API</title>")

# Modify styles in login.html to add input[type="password"]
login_html = login_html.replace('input[type="email"] {', 'input[type="email"], input[type="password"] {')
login_html = login_html.replace('input[type="email"]:focus {', 'input[type="email"]:focus, input[type="password"]:focus {')

# Remove #dashboard-view from login.html
dash_view_start = login_html.find('<!-- DASHBOARD VIEW -->')
dash_view_end = login_html.find('</main>', dash_view_start)
login_html = login_html[:dash_view_start] + login_html[dash_view_end:]

# Modify auth forms in login.html
auth_form_old = """    <div class="divider">or continue with email</div>

    <form id="login-form" onsubmit="handleMagicLink(event)">
      <div class="input-group">
        <label for="email">Work email</label>
        <input type="email" id="email" placeholder="dev@yourcompany.com" required>
      </div>
      <button type="submit" id="login-btn" class="btn-primary">Send Magic Link →</button>
    </form>
    <p id="auth-message"></p>
"""

auth_form_new = """    <div class="divider">or continue with email & password</div>

    <form id="password-form" onsubmit="handlePasswordLogin(event)">
      <div class="input-group">
        <label for="pwd-email">Email</label>
        <input type="email" id="pwd-email" placeholder="dev@yourcompany.com" required>
      </div>
      <div class="input-group">
        <label for="pwd-password">Password</label>
        <input type="password" id="pwd-password" placeholder="••••••••" required>
      </div>
      <button type="submit" id="pwd-login-btn" class="btn-primary">Sign In / Sign Up →</button>
    </form>

    <div class="divider" style="margin-top: 2rem;">or use a magic link</div>

    <form id="login-form" onsubmit="handleMagicLink(event)">
      <div class="input-group">
        <label for="email">Email for Magic Link</label>
        <input type="email" id="email" placeholder="dev@yourcompany.com" required>
      </div>
      <button type="submit" id="login-btn" class="btn-primary" style="background: var(--surface-2); border: 1px solid var(--border); color: var(--text);">Send Magic Link →</button>
    </form>
    <p id="auth-message"></p>
"""
login_html = login_html.replace(auth_form_old, auth_form_new)

# Modify JS in login.html
js_start = login_html.find('<script>')
js_code = """<script>
  const SUPABASE_URL = "{{ SUPABASE_URL }}";
  const SUPABASE_ANON_KEY = "{{ SUPABASE_ANON_KEY }}";
  const SITE_URL = "{{ NEXT_PUBLIC_SITE_URL }}" || window.location.origin;
  const sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

  sb.auth.onAuthStateChange((event, session) => {
    if (session) {
      window.location.href = '/dashboard';
    }
  });

  async function oauthLogin(provider) {
    const { error } = await sb.auth.signInWithOAuth({
      provider,
      options: { redirectTo: SITE_URL + '/auth/callback' }
    });
    if (error) alert('Error: ' + error.message);
  }

  async function handlePasswordLogin(e) {
    e.preventDefault();
    const email = document.getElementById('pwd-email').value;
    const password = document.getElementById('pwd-password').value;
    const btn = document.getElementById('pwd-login-btn');
    const msg = document.getElementById('auth-message');
    btn.disabled = true;
    btn.textContent = 'Authenticating...';
    msg.style.display = 'none';

    // Try login first
    let { data, error } = await sb.auth.signInWithPassword({ email, password });
    
    if (error && error.message.includes("Invalid login credentials")) {
        // If user doesn't exist, try sign up
        const { error: signUpError } = await sb.auth.signUp({ email, password });
        if (signUpError) {
            msg.textContent = signUpError.message;
            msg.style.color = 'var(--danger)';
            msg.style.display = 'block';
        } else {
            msg.innerHTML = '✓ Account created! <b>Please check your email to confirm your account.</b>';
            msg.style.color = 'var(--success)';
            msg.style.display = 'block';
        }
    } else if (error) {
        msg.textContent = error.message;
        msg.style.color = 'var(--danger)';
        msg.style.display = 'block';
    }
    
    btn.disabled = false;
    btn.textContent = 'Sign In / Sign Up →';
  }

  async function handleMagicLink(e) {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const btn = document.getElementById('login-btn');
    const msg = document.getElementById('auth-message');
    btn.disabled = true;
    btn.textContent = 'Sending...';

    const { error } = await sb.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: SITE_URL + '/auth/callback' }
    });

    if (error) {
      msg.textContent = error.message;
      msg.style.color = 'var(--danger)';
    } else {
      msg.textContent = '✓ Check your email for the magic link!';
      msg.style.color = 'var(--success)';
    }
    msg.style.display = 'block';
    btn.disabled = false;
    btn.textContent = 'Send Magic Link →';
  }
</script>
</body>
</html>
"""
login_html = login_html[:js_start] + js_code

with open("login.html", "w", encoding="utf-8") as f:
    f.write(login_html)


# Now strip auth stuff out of dashboard.html
# Keep styles but remove auth styles to keep it clean (or just leave them, it doesn't hurt)
# We need to remove <div id="auth-view">...</div>
auth_view_start = dash_html.find('  <!-- AUTH CARD -->')
auth_view_end = dash_html.find('  <!-- DASHBOARD VIEW -->')
new_dash_html = dash_html[:auth_view_start] + dash_html[auth_view_end:]

# Ensure dashboard-view is visible by default or let JS handle it
new_dash_html = new_dash_html.replace('display: none;', 'display: block;', 1) # First instance in #dashboard-view css

# Update JS in dashboard.html
js_start = new_dash_html.find('<script>')
js_end = new_dash_html.find('</script>', js_start)
old_js = new_dash_html[js_start:js_end]

# Modify auth state logic
new_js = old_js.replace("""  sb.auth.onAuthStateChange((event, session) => {
    if (session) {
      sessionToken = session.access_token;
      showDashboard(session.user);
      fetchKeys();
    } else {
      sessionToken = null;
      showAuth();
    }
  });""", """  sb.auth.onAuthStateChange((event, session) => {
    if (session) {
      sessionToken = session.access_token;
      showDashboard(session.user);
      fetchKeys();
    } else {
      window.location.href = '/login';
    }
  });""")

new_dash_html = new_dash_html[:js_start] + new_js + new_dash_html[js_end:]
with open("dashboard.html", "w", encoding="utf-8") as f:
    f.write(new_dash_html)


# Add /login to main.py
with open("main.py", "r", encoding="utf-8") as f:
    main_py = f.read()

login_route = """@app.get("/login", include_in_schema=False, response_class=HTMLResponse)
async def login_page():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base_dir, "login.html"), "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("{{ SUPABASE_URL }}", SUPABASE_URL or "")
        content = content.replace("{{ SUPABASE_ANON_KEY }}", SUPABASE_ANON_KEY or "")
        content = content.replace("{{ NEXT_PUBLIC_SITE_URL }}", NEXT_PUBLIC_SITE_URL)
        return HTMLResponse(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Login template not found.")

"""

if "/login" not in main_py:
    dash_idx = main_py.find('@app.get("/dashboard"')
    main_py = main_py[:dash_idx] + login_route + main_py[dash_idx:]
    with open("main.py", "w", encoding="utf-8") as f:
        f.write(main_py)

print("Split complete!")
