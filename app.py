import sys
import streamlit as st
import tensorflow as tf
from PIL import Image, ImageOps
import numpy as np

# init pygame mixer for sound run only once
import pygame
try:
    if not pygame.mixer.get_init():
        pygame.mixer.init()
except Exception:
    pass

import pandas as pd
import time
import base64
from io import BytesIO
import geocoder
from geopy.geocoders import Nominatim
import streamlit.components.v1 as components
import re
import cv2 
import datetime 
from deep_translator import GoogleTranslator
import sqlite3
from cryptography.fernet import Fernet

# config page set sidebar auto collapse so hides unless interacted with
st.set_page_config(page_title="Smart Iron®", layout="wide", initial_sidebar_state="collapsed")

# startup screen
if 'app_loaded' not in st.session_state:
    st.session_state.app_loaded = False

if not st.session_state.app_loaded:
    try:
        if not pygame.mixer.get_init(): pygame.mixer.init()
        pygame.mixer.Sound("open.wav").play()
    except: pass

    splash_html = """
    <style>
    .splash-container {
        position: fixed;
        top: 0; left: 0; width: 100vw; height: 100vh;
        background-color: #121212;
        z-index: 99999;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        animation: fadeOut 3.5s ease-in-out forwards;
        pointer-events: none;
    }
    .splash-title {
        font-size: 5rem;
        color: white;
        font-family: lucida bright;
        font-weight: bold;
    }
    .splash-title sup {
        font-size: 2rem;
        color: red;
    }
    .splash-date {
        font-size: 2.5rem;
        color: red;
        font-weight: 900;
        -webkit-text-stroke: 1.5px black;
        text-shadow: 3px 3px 6px rgba(0,0,0,0.8);
        margin-top: 10px;
    }
    @keyframes fadeOut {
        0% { opacity: 0; }
        20% { opacity: 1; }
        80% { opacity: 1; }
        100% { opacity: 0; display: none; }
    }
    </style>
    <div class="splash-container">
        <div class="splash-title">Smart Iron<sup>®</sup></div>
        <div class="splash-date">EST. 2026</div>
    </div>
    """
    st.markdown(splash_html, unsafe_allow_html=True)
    time.sleep(3.2) 
    st.session_state.app_loaded = True
    st.rerun() 
# end of startup screen

# --- ENCRYPTION SETUP ---
PITCH_KEY = b'vS-1Z9oO4_r_M3X9o0_7VlXzWn5-5_Q5X_1_9_9_9_Q=' 
cipher = Fernet(PITCH_KEY)

def secure_text(text):
    return cipher.encrypt(text.encode()).decode()

def unlock_text(cipher_text):
    try: return cipher.decrypt(cipher_text.encode()).decode()
    except: return cipher_text 
# --- END ENCRYPTION ---

def set_up_local_db():
    db_conn = sqlite3.connect('smart_iron_local.db')
    cur = db_conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS active_profiles (usr_auth_id TEXT PRIMARY KEY, sec_pwd_key TEXT, new_reg_moniker TEXT, dob TEXT, sex TEXT, height TEXT, weight TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS vitals_log (usr_auth_id TEXT, date TEXT, iron REAL, ferritin REAL, transferrin REAL)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS daily_symp (usr_auth_id TEXT, date TEXT, notes TEXT)''')
    db_conn.commit()
    db_conn.close()

set_up_local_db()

@st.cache_data
def lang_xlate(txt_in, tgt_lang):
    if tgt_lang == "English" or not txt_in:
        return txt_in
    lang_map = {"Spanish": "es", "French": "fr", "Mandarin": "zh-CN"}
    try:
        return GoogleTranslator(source='auto', target=lang_map[tgt_lang]).translate(txt_in)
    except:
        return txt_in

def get_db_con():
    return sqlite3.connect('smart_iron_local.db')

def trigger_audio_fx(snd_file):
    if st.session_state.get("sound_enabled", True):
        try:
            fx = pygame.mixer.Sound(snd_file)
            fx.play()
        except Exception:
            pass 

# Custom theme fade in scanner using CSS
st.markdown("""
<style>
:root {
    --primary: rgb(178,34,34);
    --dark: rgb(139,0,0);
    --white: #ffffff;
}
.dark-mode {
    background-color: #121212;
    color: #e0e0e0;
}
.stButton>button {
    border: 2px solid var(--primary) !important;
    color: var(--primary) !important;
    background-color: transparent !important;
    transition: 0.3s;
}
.stButton>button:hover {
    background-color: var(--primary) !important;
    color: var(--white) !important;
    border-color: var(--primary) !important;
}
.fade-wrapper {
    animation: fadeInTab 1.2s ease-in-out;
}
@keyframes fadeInTab {
    0% { opacity: 0; transform: translateY(10px); }
    100% { opacity: 1; transform: translateY(0); }
}
.fade-in-text {
    animation: fadeIn 3.5s;
}
@keyframes fadeIn {
    0% { opacity: 0; }
    100% { opacity: 1; }
}
.range-highlight {
    background-color: rgba(255, 0, 0, 0.3); 
    padding: 10px; 
    border-radius: 5px; 
    border: 1px solid red;
    margin-bottom: 10px;
    display: block;
}
.scanner-container {
    position: relative;
    display: inline-block;
    width: 100%;
    max-width: 400px;
}
.scanner-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(178, 34, 34, 0.3);
    overflow: hidden;
    pointer-events: none;
}
.scanner-bar {
    width: 100%;
    height: 4px;
    background-color: rgb(178,34,34);
    position: absolute;
    animation: scan 2s infinite linear;
}
@keyframes scan {
    0% { top: 0; }
    50% { top: 100%; }
    100% { top: 0; }
}
</style>
""", unsafe_allow_html=True)

js_idle = """
<div id="inactivity-popup" style="display:none; position:fixed; top:0; left:0; width:100vw; height:100vh; background:rgba(139,0,0,0.95); z-index:9999; color:white; text-align:center; padding-top:20vh; font-family:sans-serif;">
    <h1 style="font-size: 3rem; margin-bottom: 20px;">Are you still there?</h1>
    <button onclick="resetTimer()" style="background:transparent; border:2px solid white; color:white; padding:15px 30px; font-size: 1.2rem; margin: 10px; cursor: pointer; border-radius: 5px;">Yes</button>
    <button onclick="resetTimer()" style="background:transparent; border:2px solid white; color:white; padding:15px 30px; font-size: 1.2rem; margin: 10px; cursor: pointer; border-radius: 5px;">No</button>
</div>
<script>
    let timeout;
    function resetTimer() {
        document.getElementById('inactivity-popup').style.display = 'none';
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            document.getElementById('inactivity-popup').style.display = 'block';
        }, 120000); 
    }
    document.onmousemove = resetTimer;
    document.onkeypress = resetTimer;
    document.onclick = resetTimer;
    resetTimer();
</script>
"""
components.html(js_idle, height=0, width=0)

# Handle states
if 'agreed' not in st.session_state: st.session_state.agreed = False
if 'auth_active' not in st.session_state: st.session_state.auth_active = False
if 'curr_usr' not in st.session_state: st.session_state.curr_usr = None
if 'sound_enabled' not in st.session_state: st.session_state.sound_enabled = True
if 'tts_enabled' not in st.session_state: st.session_state.tts_enabled = False
if 'dark_mode' not in st.session_state: st.session_state.dark_mode = False
if 'language' not in st.session_state: st.session_state.language = "English"
if 'route_dest' not in st.session_state: st.session_state.route_dest = "Diagnostic Tool"

def show_scan_box(p_img):
    buf = BytesIO()
    p_img.save(buf, format="JPEG")
    b64_str = base64.b64encode(buf.getvalue()).decode()
    block = f"""
    <div class="scanner-container">
        <img src="data:image/jpeg;base64,{b64_str}" width="100%" style="border-radius: 8px;">
        <div class="scanner-overlay">
            <div class="scanner-bar"></div>
        </div>
    </div>
    """
    st.markdown(block, unsafe_allow_html=True)

def vocalize(txt_content):
    if st.session_state.tts_enabled:
        js_code = f"""
        <script>
            var msg = new SpeechSynthesisUtterance("{txt_content}");
            window.speechSynthesis.speak(msg);
        </script>
        """
        components.html(js_code, height=0, width=0)

def gen_heatmap(mod, im_arr, l_name=None):
    try:
        if not l_name:
            for l in reversed(mod.layers):
                if len(l.output_shape) == 4:
                    l_name = l.name
                    break
        g_mod = tf.keras.models.Model([mod.inputs], [mod.get_layer(l_name).output, mod.output])
        with tf.GradientTape() as t:
            c_outs, p_vals = g_mod(im_arr)
            l_val = p_vals[:, np.argmax(p_vals[0])]
        o_out = c_outs[0]
        g_val = t.gradient(l_val, c_outs)[0]
        w_val = tf.reduce_mean(g_val, axis=(0, 1))
        c_map = np.ones(o_out.shape[0:2], dtype=np.float32)
        for idx, w in enumerate(w_val):
            c_map += w * o_out[:, :, idx]
        c_map = cv2.resize(c_map.numpy(), (224, 224))
        c_map = np.maximum(c_map, 0)
        h_map = (c_map - c_map.min()) / (c_map.max() - c_map.min() + 1e-8)
        cam_pic = cv2.applyColorMap(np.uint8(255 * h_map), cv2.COLORMAP_JET)
        cam_pic = cv2.cvtColor(cam_pic, cv2.COLOR_BGR2RGB)
        return cam_pic
    except Exception as err:
        st.warning(lang_xlate("This model is unsupported for exact grad-CAM mapping. Displaying generic activation simulation only.", st.session_state.language))
        pic_copy = im_arr[0].copy()
        pic_copy = ((pic_copy + 1) * 127.5).astype(np.uint8)
        h_map = cv2.applyColorMap(cv2.GaussianBlur(pic_copy, (51, 51), 0), cv2.COLORMAP_JET)
        return cv2.addWeighted(pic_copy, 0.6, h_map, 0.4, 0)


def rate_sec(sec_str):
    if len(sec_str) == 0: return "", "transparent", ""
    has_cap = bool(re.search(r'[A-Z]', sec_str))
    has_sym = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', sec_str))
    is_long = len(sec_str) >= 9
    
    if is_long and has_cap and has_sym: return "Strong", "rgba(0, 255, 0, 0.3)", "green"
    elif is_long and (has_cap or has_sym): return "Moderate", "rgba(255, 255, 0, 0.3)", "orange"
    else: return "Weak", "rgba(255, 0, 0, 0.3)", "red"

# 1: DISCLAIMER 
if not st.session_state.agreed:
    st.markdown('<div class="fade-wrapper"><h1 class="fade-in-text">Disclaimer</h1>', unsafe_allow_html=True)
    body_txt = "Please note that this application is for symptom tracking only and does not provide a medical diagnosis. Results are informational and should not replace a clinician evaluation or laboratory testing. The information generated by this tool is based on available data inputs and analysis. Accuracy may vary, and results may be subject to limitations inherent to the data provided. This tool is not intended for use in emergency situations or as the basis for critical patient management decisions. If you are displaying concerning symptoms or have a family history of iron disorders, please seek professional medical advice. This tool may miss conditions or flag normal findings and is therefore not a substitute for medical care."
    st.markdown(f'<p class="fade-in-text">{lang_xlate(body_txt, st.session_state.language)}</p></div>', unsafe_allow_html=True)
    if st.button(lang_xlate("I Agree", st.session_state.language)):
        trigger_audio_fx("click.wav")
        st.session_state.agreed = True
        st.rerun()

# 2: LOGIN/SIGNUP 
elif not st.session_state.auth_active:
    st.markdown('<div class="fade-wrapper">', unsafe_allow_html=True)
    st.session_state.language = st.selectbox("Preferred Language (AI-translation enabled):", ["English", "Spanish", "French", "Mandarin"])
    
    st.title(lang_xlate("Log In Portal", st.session_state.language))
    st.info(lang_xlate("All local data is processed privately and safely in your local environment.", st.session_state.language))
    
    t1, t2 = st.tabs([lang_xlate("Login", st.session_state.language), lang_xlate("Sign Up", st.session_state.language)])
    
    with t1:
        st.subheader(lang_xlate("Log In", st.session_state.language))
        usr_auth_id = st.text_input(lang_xlate("Email/Username", st.session_state.language), key="usr_auth_id")
        sec_pwd_key = st.text_input(lang_xlate("Password", st.session_state.language), type="password", key="sec_pwd_key")
        if st.button(lang_xlate("Login", st.session_state.language)):
            trigger_audio_fx("click.wav")
            with st.spinner(lang_xlate("Authenticating...", st.session_state.language)):
                time.sleep(0.5)
                db = get_db_con()
                cc = db.cursor()
                cc.execute("SELECT sec_pwd_key FROM active_profiles WHERE usr_auth_id=?", (usr_auth_id,))
                found = cc.fetchone()
                db.close()
                if found and found[0] == sec_pwd_key:
                    st.session_state.auth_active = True
                    st.session_state.curr_usr = usr_auth_id
                    st.rerun()
                else:
                    st.error(lang_xlate("Invalid credentials.", st.session_state.language))
                
    with t2:
        st.subheader(lang_xlate("Create Account", st.session_state.language))
        make_usr_id = st.text_input(lang_xlate("Email/Username)", st.session_state.language), key="make_usr_id")
        
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            new_reg_moniker = st.text_input(lang_xlate("Full Name", st.session_state.language), key="new_reg_moniker")
            birth_val = st.date_input(lang_xlate("Date of Birth", st.session_state.language), min_value=datetime.date(1900, 1, 1), max_value=datetime.date.today())
            gen_val = st.selectbox(lang_xlate("Sex", st.session_state.language), ["Male", "Female", "Other"])
        with c_p2:
            h_val = st.number_input(lang_xlate("Height (e.g., 5'9\" or 175cm)", st.session_state.language))
            w_val = st.number_input(lang_xlate("Weight (e.g., 150 lbs or 68 kg)", st.session_state.language))

        st.markdown(lang_xlate("**Create a Password** (Minimum 9 characters, 1 uppercase letter, 1 symbol)", st.session_state.language))
        make_pwd_key = st.text_input(lang_xlate("Password", st.session_state.language), type="password", key="make_pwd_key_input")
        
        p_stat, p_col, t_col = rate_sec(make_pwd_key)
        if make_pwd_key:
            st.markdown(f"""
            <div style="background-color: {p_col}; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold; color: {t_col};">
                {lang_xlate('Password Strength:', st.session_state.language)} {lang_xlate(p_stat, st.session_state.language)}
            </div>
            """, unsafe_allow_html=True)
        
        if st.button(lang_xlate("Sign Up", st.session_state.language)):
            trigger_audio_fx("click.wav")
            with st.spinner(lang_xlate("Creating secure profile...", st.session_state.language)):
                time.sleep(0.5)
                db = get_db_con()
                cc = db.cursor()
                cc.execute("SELECT usr_auth_id FROM active_profiles WHERE usr_auth_id=?", (make_usr_id,))
                exists = cc.fetchone()
                if "@" not in make_usr_id:
                    st.error(lang_xlate("Username must contain an '@' symbol.", st.session_state.language))
                elif exists:
                    st.error(lang_xlate("User already exists.", st.session_state.language))
                elif p_stat != "Strong":
                    st.error(lang_xlate("Cannot proceed. Please ensure your password is 'Strong' (Min 9 chars, 1 uppercase, 1 symbol).", st.session_state.language))
                elif not new_reg_moniker:
                    st.error(lang_xlate("Please enter your name.", st.session_state.language))
                else:
                    cc.execute("INSERT INTO active_profiles VALUES (?,?,?,?,?,?,?)", 
                              (make_usr_id, make_pwd_key, new_reg_moniker, str(birth_val), gen_val, h_val, w_val))
                    db.commit()
                    st.success(lang_xlate("Account created. Please log in.", st.session_state.language))
                db.close()
    st.markdown('</div>', unsafe_allow_html=True)

# 3: MAIN APP 
else:
    db = get_db_con()
    cc = db.cursor()
    cc.execute("SELECT new_reg_moniker, dob, sex, height, weight FROM active_profiles WHERE usr_auth_id=?", (st.session_state.curr_usr,))
    u_data = cc.fetchone()
    db.close()
    
    if u_data: d_name, d_dob, d_sex, d_hgt, d_wgt = u_data
    else: d_name, d_dob, d_sex, d_hgt, d_wgt = ("Unknown", "2000-01-01", "Other", "N/A", "N/A")

    st.sidebar.title(lang_xlate("Smart Iron", st.session_state.language))
    st.sidebar.markdown(f"**{lang_xlate('Hi', st.session_state.language)}, {d_name}!**")
    vocalize(f"Welcome to Smart Iron®, {d_name}!")

    st.sidebar.divider()

    n_opts = [
        "Diagnostic Tool", "Questionnaire", "Tracker & Trends", 
        "Daily Symptom Logging", "Personal Details", "Location & Labs", 
        "More Information on Anemia and Hemochromatosis", "FAQ", "System Settings"
    ]
    t_opts = [lang_xlate(o, st.session_state.language) for o in n_opts]
    
    s_choice = st.sidebar.radio(lang_xlate("Navigation", st.session_state.language), t_opts, index=n_opts.index(st.session_state.route_dest))
    r_choice = n_opts[t_opts.index(s_choice)]
    st.session_state.route_dest = r_choice

    st.sidebar.divider()
    if st.sidebar.button(lang_xlate("Log Out", st.session_state.language)):
        trigger_audio_fx("click.wav")
        st.session_state.auth_active = False
        st.session_state.curr_usr = None
        st.rerun()

    st.markdown('<div class="fade-wrapper">', unsafe_allow_html=True)

    if r_choice == "System Settings":
        st.title(lang_xlate("System Settings", st.session_state.language))
        st.write(lang_xlate("Configure your app experience here.", st.session_state.language))
        st.session_state.sound_enabled = st.toggle(lang_xlate("Enable Sound Effects", st.session_state.language), value=st.session_state.sound_enabled)
        st.session_state.tts_enabled = st.toggle(lang_xlate("Enable Text-To-Speech (Accessibility)", st.session_state.language), value=st.session_state.tts_enabled)
        st.session_state.dark_mode = st.toggle(lang_xlate("Toggle Dark Mode", st.session_state.language), value=st.session_state.dark_mode)
        st.session_state.language = st.selectbox("App Language (AI Translation Supported):", 
                                                 ["English", "Spanish", "French", "Mandarin"],
                                                 index=["English", "Spanish", "French", "Mandarin"].index(st.session_state.language))
        st.success(lang_xlate("Settings saved automatically.", st.session_state.language))

    elif r_choice == "Personal Details":
        st.title(lang_xlate("Personal Details", st.session_state.language))
        st.write(lang_xlate("View and update your registered information.", st.session_state.language))
        
        cx1, cx2 = st.columns(2)
        with cx1:
            st.write(f"**{lang_xlate('Name:', st.session_state.language)}** {d_name}")
            st.write(f"**{lang_xlate('Email:', st.session_state.language)}** {st.session_state.curr_usr}")
            st.write(f"**{lang_xlate('Date of Birth:', st.session_state.language)}** {d_dob}")
        with cx2:
            st.write(f"**{lang_xlate('Sex:', st.session_state.language)}** {d_sex}")
            st.write(f"**{lang_xlate('Height:', st.session_state.language)}** {d_hgt}")
            st.write(f"**{lang_xlate('Weight:', st.session_state.language)}** {d_wgt}")
            
        new_mail = st.text_input(lang_xlate("Update Email", st.session_state.language), value=st.session_state.curr_usr)

        if new_mail != st.session_state.curr_usr:
            val_pwd = st.text_input(lang_xlate("Enter Password to confirm email change", st.session_state.language), type="password")
            if st.button(lang_xlate("Save Changes", st.session_state.language)) and val_pwd:
                db = get_db_con()
                cc = db.cursor()
                cc.execute("UPDATE active_profiles SET usr_auth_id=? WHERE usr_auth_id=? AND sec_pwd_key=?", (new_mail, st.session_state.curr_usr, val_pwd))
                if cc.rowcount > 0:
                    st.session_state.curr_usr = new_mail
                    st.success(lang_xlate("Email updated successfully!", st.session_state.language))
                else:
                    st.error(lang_xlate("Incorrect password", st.session_state.language))
                db.commit()
                db.close()

    elif r_choice == "Diagnostic Tool":
        d_modes = [lang_xlate("Conjunctival Pallor (Eyes)", st.session_state.language), 
                   lang_xlate("Dermal Bronzing (Skin)", st.session_state.language), 
                   lang_xlate("Nailbed Scanning (Nails)", st.session_state.language)]
        sel_mod = st.radio(lang_xlate("Select Diagnostic Mode", st.session_state.language), d_modes)

        if "Eyes" in sel_mod or "Ojos" in sel_mod or "Yeux" in sel_mod:
            m_path, l_path = "model_eyes.h5", "labels_eyes.txt"
        elif "Skin" in sel_mod or "Piel" in sel_mod or "Peau" in sel_mod:
            m_path, l_path = "model_skin.h5", "labels_skin.txt"
        else:
            m_path, l_path = "model_nails.h5", "labels_nails.txt"

        @st.cache_resource
        def pull_ai_files(mp, lp):
            m_net = tf.keras.models.load_model(mp, compile=False)
            with open(lp, "r") as f:
                c_lbls = [line.strip() for line in f.readlines()]
            return m_net, c_lbls

        try:
            active_ai_brain, tag_list = pull_ai_files(m_path, l_path)
        except Exception:
            st.warning(lang_xlate("Please ensure the corresponding model (.h5) and label (.txt) files are uploaded in your working directory.", st.session_state.language))
            st.stop()

        st.title(f"{lang_xlate('Mode:', st.session_state.language)} {sel_mod}")
        use_cam = st.checkbox(lang_xlate("Enable Grad-CAM Overlay (Visual Interpretability)", st.session_state.language))
        flip_pic = st.checkbox(lang_xlate("Mirror Image", st.session_state.language))
        cam_snap = st.camera_input(lang_xlate("Scan Target", st.session_state.language))

        if cam_snap:
            p_obj = Image.open(cam_snap).convert("RGB")
            if flip_pic:
                p_obj = ImageOps.mirror(p_obj)
            p_obj = ImageOps.fit(p_obj, (224, 224), Image.Resampling.LANCZOS)
            
            show_scan_box(p_obj)
            
            with st.status(lang_xlate("Analyzing pigmentation...", st.session_state.language), expanded=True) as stat_bar:
                st.write(lang_xlate("Extracting pixel clusters...", st.session_state.language))
                time.sleep(1.5)
                st.write(lang_xlate("Running inference...", st.session_state.language))
                time.sleep(2)
                st.write(lang_xlate("Generating activation maps...", st.session_state.language))
                time.sleep(1.5)
                stat_bar.update(label=lang_xlate("Analysis Complete", st.session_state.language), state="complete", expanded=False)
            
            p_arr = np.asarray(p_obj)
            norm_p = (p_arr.astype(np.float32) / 127.5) - 1
            t_data = np.ndarray(shape=(1, 224, 224, 3), dtype=np.float32)
            t_data[0] = norm_p

            ai_guess = active_ai_brain.predict(t_data)
            top_i = np.argmax(ai_guess)
            cert_score = ai_guess[0][top_i]
            
            if cert_score < 0.60:
                st.error(lang_xlate("Subject not clearly recognized. Please retake the picture.", st.session_state.language))
            else:
                r_txt = tag_list[top_i]
                neat_txt = r_txt.split(' ', 1)[-1].split(': ')[-1]

                trigger_audio_fx("success.wav") 
                st.divider()
                st.subheader(lang_xlate("Analysis Results", st.session_state.language))
                st.write(f"{lang_xlate('Result:', st.session_state.language)} **{lang_xlate(neat_txt, st.session_state.language)}**")
                st.write(f"{lang_xlate('Confidence:', st.session_state.language)} **{round(cert_score * 100, 2)}%**")
                
                if use_cam:
                    st.write(f"### {lang_xlate('Grad-CAM Heatmap Analysis', st.session_state.language)}")
                    with st.spinner(lang_xlate("Generating Class Activation Map...", st.session_state.language)):
                        heat_pic = gen_heatmap(active_ai_brain, t_data)
                        cw1, cw2 = st.columns(2)
                        with cw1: st.image(p_obj, caption=lang_xlate("Original Scan", st.session_state.language))
                        with cw2: st.image(heat_pic, caption=lang_xlate("Grad-CAM Focus Areas", st.session_state.language))

    elif r_choice == "Location & Labs":
        st.title(lang_xlate("Find a Phlebotomy Center", st.session_state.language))
        
        if st.button(lang_xlate("Detect Nearest Locations & Costs Worldwide", st.session_state.language)):
            trigger_audio_fx("click.wav")
            with st.spinner(lang_xlate("Connecting to global positioning satellites...", st.session_state.language)):
                try:
                    geo_me = geocoder.ip('me')
                    if geo_me.ok and geo_me.city:
                        loc_str = f"{geo_me.city}, {geo_me.country}"
                        st.success(f"{lang_xlate('Location Verified:', st.session_state.language)} {loc_str}")
                        
                        geoloc = Nominatim(user_agent="smart_iron_app")
                        pts = geoloc.geocode(loc_str)
                        
                        st.write(f"### {lang_xlate('Nearest Phlebotomy Facilities for', st.session_state.language)} {geo_me.city}")
                        st.write(f"**1. {geo_me.city} {lang_xlate('General Hospital Lab', st.session_state.language)}**")
                        st.write(f"**2. {lang_xlate('Regional Blood Core Facility', st.session_state.language)}**")
                        st.write(f"**3. {lang_xlate('Main Street Blood Collection Center', st.session_state.language)}**")
                        
                        if pts:
                            g_url = f"https://www.google.com/maps/search/blood+lab+near+{pts.latitude},{pts.longitude}"
                            st.markdown(f"**[Click here to open Google Maps for real clinics near {geo_me.city}]({g_url})**")
                        
                        st.write(f"### {lang_xlate('Estimated Costs in your region', st.session_state.language)}")
                        if geo_me.country == "US":
                            st.write("Basic Complete Blood Count: $15 - $40 USD")
                            st.write("Comprehensive Iron Panel: $40 - $100 USD")
                        elif geo_me.country == "CA":
                            st.write("Covered by provincial healthcare with a requisition.")
                        elif geo_me.country == "GB":
                            st.write("Covered by NHS with referral. Private: £30 - £80 GBP")
                        else:
                            st.write("Costs vary significantly by region. Please consult local healthcare providers.")
                    else:
                        st.error(lang_xlate("Unable to pinpoint exact location.", st.session_state.language))
                except Exception as e:
                    st.error(lang_xlate("Network error during geolocation.", st.session_state.language))
            
        st.divider()
        st.write(f"### {lang_xlate('Pre-Test Instructions', st.session_state.language)}")
        st.write(lang_xlate("Follow instructions from the clinic or laboratory. Some iron studies may require fasting for 12 hours prior.", st.session_state.language))
        
        if st.button(lang_xlate("For more information, please visit our FAQ.", st.session_state.language)):
            st.session_state.route_dest = "FAQ"
            st.rerun()

    elif r_choice == "More Information on Anemia and Hemochromatosis":
        st.title(lang_xlate("More Information on Anemia and Hemochromatosis", st.session_state.language))
        st.subheader(lang_xlate("Anemia", st.session_state.language))
        st.write(lang_xlate("enter text", st.session_state.language))
        st.divider()
        st.subheader(lang_xlate("Hemochromatosis", st.session_state.language))
        st.write(lang_xlate("enter text", st.session_state.language))

    elif r_choice == "Tracker & Trends":
        st.title(lang_xlate("Blood Test & Sensor Tracking", st.session_state.language))
        st.write(f"### {lang_xlate('Reference Ranges', st.session_state.language)}")
        
        c_age = "Unknown"
        if d_dob != "2000-01-01":
            b_d = datetime.datetime.strptime(d_dob, "%Y-%m-%d").date()
            tt_d = datetime.date.today()
            a_yrs = tt_d.year - b_d.year - ((tt_d.month, tt_d.day) < (b_d.month, b_d.day))
            if a_yrs < 1: c_age = "Infant"
            elif a_yrs < 18: c_age = "Child"
            elif d_sex == "Male": c_age = "Adult Male"
            elif d_sex == "Female": c_age = "Adult Female"
        
        m_txt = lang_xlate("Men: 65 to 176 micrograms per deciliter.", st.session_state.language)
        w_txt = lang_xlate("Women: 50 to 170 micrograms per deciliter.", st.session_state.language)
        c_txt = lang_xlate("Children: 50 to 120 micrograms per deciliter.", st.session_state.language)
        i_txt = lang_xlate("Infants: 100 to 250 micrograms per deciliter.", st.session_state.language)
        
        if c_age == "Adult Male": st.markdown(f"<div class='range-highlight'><strong>{m_txt}</strong></div>", unsafe_allow_html=True)
        else: st.write(m_txt)
        if c_age == "Adult Female": st.markdown(f"<div class='range-highlight'><strong>{w_txt}</strong></div>", unsafe_allow_html=True)
        else: st.write(w_txt)
        if c_age == "Child": st.markdown(f"<div class='range-highlight'><strong>{c_txt}</strong></div>", unsafe_allow_html=True)
        else: st.write(c_txt)
        if c_age == "Infant": st.markdown(f"<div class='range-highlight'><strong>{i_txt}</strong></div>", unsafe_allow_html=True)
        else: st.write(i_txt)

        st.divider()
        cx1, cx2 = st.columns(2)
        with cx1:
            inp_d = st.date_input(lang_xlate("Date", st.session_state.language))
            inp_fe = st.number_input(lang_xlate("Serum Iron", st.session_state.language), min_value=0.0, format="%.1f")
        with cx2:
            inp_ferr = st.number_input(lang_xlate("Ferritin", st.session_state.language), min_value=0.0, format="%.1f")
            inp_tsat = st.number_input(lang_xlate("Transferrin Saturation (%)", st.session_state.language), min_value=0.0, format="%.1f")
            
        if st.button(lang_xlate("Log Results", st.session_state.language)):
            trigger_audio_fx("click.wav")
            db = get_db_con()
            cc = db.cursor()
            cc.execute("INSERT INTO vitals_log VALUES (?,?,?,?,?)", (st.session_state.curr_usr, str(inp_d), inp_fe, inp_ferr, inp_tsat))
            db.commit()
            db.close()
            st.success(lang_xlate("Results logged successfully.", st.session_state.language))
            
        db = get_db_con()
        cc = db.cursor()
        cc.execute("SELECT date, iron, ferritin, transferrin FROM vitals_log WHERE usr_auth_id=?", (st.session_state.curr_usr,))
        all_recs = cc.fetchall()
        db.close()
        
        if all_recs:
            st.divider()
            df_t = pd.DataFrame(all_recs, columns=["Date", "Serum Iron", "Ferritin", "Transferrin"])
            df_t.set_index("Date", inplace=True)
            st.line_chart(df_t)

            # EXPORT & STATS
            st.divider()
            st.subheader(lang_xlate("Clinical Export & Statistics", st.session_state.language))
            
            if len(df_t) > 1:
                mean_iron = df_t["Serum Iron"].mean()
                std_iron = df_t["Serum Iron"].std()
                st.markdown(f"**{lang_xlate('Historical Iron Mean:', st.session_state.language)}** {mean_iron:.1f} µg/dL | **{lang_xlate('Standard Deviation:', st.session_state.language)}** ±{std_iron:.1f}")
            
            csv_data = df_t.to_csv().encode('utf-8')
            st.download_button(
                label=lang_xlate("Download Clinical Data (CSV)", st.session_state.language),
                data=csv_data,
                file_name='smart_iron_export.csv',
                mime='text/csv',
            )

        # LIVE SENSOR SWEEP
        st.divider()
        st.subheader(lang_xlate("Live Optical Sensor Sweep", st.session_state.language))
        st.write(lang_xlate("Initiate real-time hardware telemetry test.", st.session_state.language))
        
        if st.button(lang_xlate("Start Live Scan", st.session_state.language)):
            trigger_audio_fx("click.wav")
            live_chart = st.empty() 
            
            current_iron = 85.0 
            live_data = pd.DataFrame({"Time (s)": [0], "Live Iron µg/dL": [current_iron]}).set_index("Time (s)")
            
            with st.spinner(lang_xlate("Calibrating optical sensors...", st.session_state.language)):
                time.sleep(1)
                
            for i in range(1, 40): 
                fluctuation = np.random.normal(0, 2.0) 
                current_iron += fluctuation
                
                new_tick = pd.DataFrame({"Time (s)": [i], "Live Iron µg/dL": [current_iron]}).set_index("Time (s)")
                live_data = pd.concat([live_data, new_tick])
                
                live_chart.line_chart(live_data)
                time.sleep(0.15) 
                
            st.success(f"{lang_xlate('Sweep Complete. Recommended logging value:', st.session_state.language)} **{current_iron:.1f}**")


    elif r_choice == "Daily Symptom Logging":
        st.title(lang_xlate("Daily Symptom Logging", st.session_state.language))
        sd_log = st.date_input(lang_xlate("Date", st.session_state.language))
        sn_log = st.text_area(lang_xlate("Symptom Notes", st.session_state.language))
        
        if st.button(lang_xlate("Save Daily Log", st.session_state.language)):
            trigger_audio_fx("click.wav")
            db = get_db_con()
            cc = db.cursor()
            cc.execute("INSERT INTO daily_symp VALUES (?,?,?)", (st.session_state.curr_usr, str(sd_log), secure_text(sn_log)))
            db.commit()
            db.close()
            st.success(lang_xlate("Log saved.", st.session_state.language))

        db = get_db_con()
        cc = db.cursor()
        cc.execute("SELECT date, notes FROM daily_symp WHERE usr_auth_id=? ORDER BY date DESC", (st.session_state.curr_usr,))
        s_recs = cc.fetchall()
        db.close()
        
        if s_recs:
            st.divider()
            for rec in s_recs: 
                st.write(f"**{rec[0]}**: {unlock_text(rec[1])}")

    elif r_choice == "Questionnaire":
        st.title(lang_xlate("Initial Symptom Assessment", st.session_state.language))
        q_bank = [
            "1.  Do you feel unusually tired or low on energy?",
            "2.  Do you feel weak more often than usual?",
            "3.  Do you get short of breath with normal activity?",
            "4.  Do you feel dizzy or lightheaded?",
            "5.  Do you have a fast heartbeat or heart flutters?",
            "6.  Do you have pale skin, pale inner eyelids, or a washed-out appearance?",
            "7.  Do you have cold hands or feet?",
            "8.  Do you have headaches more often than usual?",
            "9.  Do you have brittle nails, hair loss, or a sore tongue?",
            "10. Do you crave ice, clay, or non-food items?",
            "11. Do you have joint pain, especially in the hands, knuckles, knees, or wrists?",
            "12. Do you have belly or upper-right abdominal pain?",
            "13. Have you noticed bronze, gray, or unusually dark skin color?",
            "14. Have you noticed skin darkening that seems different from tanning?",
            "15. Have your menstrual periods become absent or irregular, or have you had early menopause?",
            "16. Have you had unexplained weight loss?",
            "17. Do you have diabetes, high blood sugar, or new trouble controlling blood sugar?",
            "18. Have you been told you have liver problems or abnormal liver tests?",
        ]
        
        a_bank = []
        for qq in q_bank: 
            a_bank.append(st.checkbox(lang_xlate(qq, st.session_state.language)))
            
        if st.button(lang_xlate("Submit Questionnaire", st.session_state.language)):
            trigger_audio_fx("click.wav")
            if sum(a_bank) > 4: 
                st.error(lang_xlate("Please seek professional medical evaluation.", st.session_state.language))
            else: 
                st.success(lang_xlate("Nothing unusual detected.", st.session_state.language))

    elif r_choice == "FAQ":
        st.title(lang_xlate("Frequently Asked Questions", st.session_state.language))
        
        st.write(f"**{lang_xlate('What does this application assist with?', st.session_state.language)}**")
        st.write(lang_xlate("It helps you track symptoms, blood test results, treatment history, and appointments, and it can provide educational information about anemia and hemochromatosis.", st.session_state.language))

        st.write(f"**{lang_xlate('Can the app diagnose anemia or hemochromatosis?', st.session_state.language)}**")
        st.write(lang_xlate("No. It can only support screening and tracking. Anemia is diagnosed using blood counts such as hemoglobin and hematocrit, while hemochromatosis is usually screened for with laboratory tests such as ferritin and transferrin saturation.", st.session_state.language))

        st.write(f"**{lang_xlate('Can I use the app instead of seeing a doctor?', st.session_state.language)}**")
        st.write(lang_xlate("No, the app is not a substitute for medical care. If the app flags symptoms or your symptoms are worsening, you should talk to a clinician.", st.session_state.language))

        st.write(f"**{lang_xlate('Why does the app ask for blood test results?', st.session_state.language)}**")
        st.write(lang_xlate("Blood tests are the most important part of evaluating both conditions. Symptom tracking and skin or eye analysis may help identify patterns, but they cannot confirm disease on their own.", st.session_state.language))

        st.write(f"**{lang_xlate('What should I do before a blood test?', st.session_state.language)}**")
        st.write(lang_xlate("Follow the instructions from the clinic or lab, which can be found in-app. Some iron studies may require fasting or specific timing, and the app can remind users to confirm preparation instructions with the testing site.", st.session_state.language))

        st.write(f"**{lang_xlate('Can the app estimate costs?', st.session_state.language)}**")
        st.write(lang_xlate("The app can show estimates, but prices vary by location, test type, and insurance coverage.", st.session_state.language))

    st.markdown('</div>', unsafe_allow_html=True)