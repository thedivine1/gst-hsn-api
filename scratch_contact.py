import sys

with open(r'c:\Users\chaitanya.patankar\gst-hsn-api\terms.html', 'r', encoding='utf-8') as f:
    content = f.read()

header = content.split('<main class="page-main">')[0]
footer = '<footer>' + content.split('<footer>')[1]

contact_content = '''<main class="page-main">
  <div class="legal-container">
    <div class="legal-header">
      <h1>Contact Us</h1>
      <p>Have questions? We'd love to hear from you.</p>
    </div>
    
    <div class="legal-content" style="max-width: 600px; margin: 0 auto; background: var(--surface); padding: 2rem; border-radius: 12px; border: 1px solid var(--border);">
      <form action="#" method="POST" style="display: flex; flex-direction: column; gap: 1.25rem;" onsubmit="event.preventDefault(); alert('Thanks for contacting us! We will get back to you shortly.'); this.reset();">
        <div>
          <label style="display: block; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.5rem;">Your Name</label>
          <input type="text" placeholder="John Doe" style="width: 100%; padding: 0.75rem; border-radius: 6px; background: var(--bg); border: 1px solid var(--border); color: var(--text); font-family: inherit;" required>
        </div>
        <div>
          <label style="display: block; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.5rem;">Email Address</label>
          <input type="email" placeholder="john@example.com" style="width: 100%; padding: 0.75rem; border-radius: 6px; background: var(--bg); border: 1px solid var(--border); color: var(--text); font-family: inherit;" required>
        </div>
        <div>
          <label style="display: block; font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.5rem;">Message</label>
          <textarea rows="5" placeholder="How can we help you?" style="width: 100%; padding: 0.75rem; border-radius: 6px; background: var(--bg); border: 1px solid var(--border); color: var(--text); font-family: inherit; resize: vertical;" required></textarea>
        </div>
        <button type="submit" style="background: var(--amber); color: #fff; padding: 0.85rem; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; transition: all 0.2s; font-family: inherit;">Send Message</button>
      </form>
      
      <div style="margin-top: 2rem; padding-top: 2rem; border-top: 1px solid var(--border); text-align: center; color: var(--text-muted); font-size: 0.9rem;">
        <p>Or email us directly at <a href="mailto:support@gstaccelerator.in" style="color: var(--amber); text-decoration: none;">support@gstaccelerator.in</a></p>
      </div>
    </div>
  </div>
</main>
'''

full_html = header + contact_content + footer

with open(r'c:\Users\chaitanya.patankar\gst-hsn-api\contact.html', 'w', encoding='utf-8') as f:
    f.write(full_html)
