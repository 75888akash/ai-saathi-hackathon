(function() {
  const widgetHTML = `
    <div id="ai-saathi-widget" style="position:fixed;bottom:20px;right:20px;z-index:9999;font-family:Arial,sans-serif;">
      <button id="ai-saathi-btn" style="width:65px;height:65px;border-radius:50%;background:linear-gradient(135deg,#667eea,#764ba2);border:none;cursor:pointer;box-shadow:0 4px 15px rgba(0,0,0,0.3);font-size:32px;transition:all 0.3s;">🤖</button>
      
      <div id="ai-saathi-window" style="display:none;position:absolute;bottom:85px;right:0;width:360px;height:520px;background:white;border-radius:20px;box-shadow:0 10px 50px rgba(0,0,0,0.3);flex-direction:column;overflow:hidden;">
        <div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:18px;display:flex;justify-content:space-between;align-items:center;">
          <div>
            <div style="font-weight:bold;font-size:18px;">🤖 AI Saathi</div>
            <div style="font-size:12px;opacity:0.9;">आपका डिजिटल सहायक</div>
          </div>
          <button id="ai-saathi-close" style="background:none;border:none;color:white;font-size:28px;cursor:pointer;line-height:1;">×</button>
        </div>
        
        <div id="ai-saathi-messages" style="flex:1;padding:15px;overflow-y:auto;background:#f8f9fa;">
          <div style="text-align:center;color:#999;padding:30px 20px;">
            <div style="font-size:50px;margin-bottom:15px;">👋</div>
            <div style="font-size:15px;font-weight:600;margin-bottom:5px;">नमस्ते! मैं आपकी मदद के लिए यहाँ हूँ</div>
            <div style="font-size:13px;">Ask about government schemes</div>
          </div>
        </div>
        
        <div style="padding:15px;background:white;border-top:1px solid #e5e7eb;">
          <select id="ai-saathi-lang" style="width:100%;padding:10px;border:2px solid #e5e7eb;border-radius:10px;margin-bottom:10px;font-size:14px;font-weight:600;">
            <option value="hi">🇮🇳 हिंदी (Hindi)</option>
            <option value="en">🇬🇧 English</option>
          </select>
          <div style="display:flex;gap:8px;margin-bottom:10px;">
            <input id="ai-saathi-input" type="text" placeholder="अपना सवाल लिखें..." style="flex:1;padding:12px;border:2px solid #e5e7eb;border-radius:25px;outline:none;font-size:14px;">
            <button id="ai-saathi-mic" style="background:linear-gradient(135deg,#f093fb,#f5576c);color:white;border:none;border-radius:50%;width:45px;height:45px;cursor:pointer;font-size:18px;">🎤</button>
            <button id="ai-saathi-send" style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;border:none;border-radius:50%;width:45px;height:45px;cursor:pointer;font-size:20px;">📤</button>
          </div>
          <button id="ai-saathi-stop" style="display:none;width:100%;background:#ef4444;color:white;border:none;border-radius:25px;padding:10px;cursor:pointer;font-size:13px;font-weight:700;">⏹️ रोकें | Stop Audio</button>
        </div>
      </div>
    </div>
  `;
  
  document.body.insertAdjacentHTML('beforeend', widgetHTML);
  
  const btn = document.getElementById('ai-saathi-btn');
  const chatWindow = document.getElementById('ai-saathi-window');
  const close = document.getElementById('ai-saathi-close');
  const input = document.getElementById('ai-saathi-input');
  const send = document.getElementById('ai-saathi-send');
  const messages = document.getElementById('ai-saathi-messages');
  const micBtn = document.getElementById('ai-saathi-mic');
  const stopBtn = document.getElementById('ai-saathi-stop');
  const langSelect = document.getElementById('ai-saathi-lang');
  
  const textApiUrl = "https://jg30c7c6r7.execute-api.ap-south-1.amazonaws.com/prod/ask";
  const audioApiUrl = "https://jg30c7c6r7.execute-api.ap-south-1.amazonaws.com/prod/audio";
  
  let recognition = null;
  
  function updatePlaceholder() {
    input.placeholder = langSelect.value === 'en' ? 'Type your question...' : 'अपना सवाल लिखें...';
  }
  
  langSelect.onchange = updatePlaceholder;
  input.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };
  updatePlaceholder();
  
  btn.onclick = () => {
    chatWindow.style.display = chatWindow.style.display === 'none' ? 'flex' : 'none';
    btn.style.transform = chatWindow.style.display === 'flex' ? 'scale(0.9)' : 'scale(1)';
  };
  
  close.onclick = () => {
    chatWindow.style.display = 'none';
    btn.style.transform = 'scale(1)';
  };
  
  stopBtn.onclick = () => {
    const globalAudio = window.aiSaathiAudio;
    if (globalAudio) {
      globalAudio.pause();
      globalAudio.currentTime = 0;
      window.aiSaathiAudio = null;
      stopBtn.style.display = 'none';
      document.querySelectorAll('.widget-listen-btn').forEach(btn => {
        btn.innerHTML = '🔊 सुनें';
        btn.style.background = '#4caf50';
        btn.disabled = false;
      });
    }
  };
  
  micBtn.onclick = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('आपका ब्राउज़र वॉइस को सपोर्ट नहीं करता | Voice not supported');
      return;
    }
    
    recognition = new SpeechRecognition();
    recognition.lang = langSelect.value === 'hi' ? 'hi-IN' : 'en-IN';
    recognition.continuous = false;
    recognition.interimResults = false;
    
    micBtn.style.animation = 'pulse 1s infinite';
    const listeningMsg = langSelect.value === 'en' ? '🎤 Listening...' : '🎤 सुन रहा हूं...';
    messages.innerHTML += `<div id="listening" style="background:#fef3c7;color:#d97706;padding:12px 18px;border-radius:15px;margin-bottom:12px;text-align:center;font-weight:600;">${listeningMsg}</div>`;
    messages.scrollTop = messages.scrollHeight;
    
    recognition.start();
    
    recognition.onresult = (event) => {
      const text = event.results[0][0].transcript;
      input.value = text;
      recognition.stop();
      micBtn.style.animation = '';
      document.getElementById('listening')?.remove();
      sendMessage(true);
    };
    
    recognition.onerror = () => {
      recognition.stop();
      micBtn.style.animation = '';
      document.getElementById('listening')?.remove();
    };
    
    recognition.onend = () => {
      micBtn.style.animation = '';
    };
  };
  
  async function sendMessage(autoPlayAudio = false) {
    const query = input.value.trim();
    if (!query) return;
    
    const selectedLang = langSelect.value;
    
    messages.innerHTML += `<div style="background:#667eea;color:white;padding:12px 18px;border-radius:18px;margin-bottom:12px;max-width:75%;margin-left:auto;text-align:right;font-size:14px;">${query}</div>`;
    input.value = '';
    messages.scrollTop = messages.scrollHeight;
    
    messages.innerHTML += `<div id="thinking" style="background:#dbeafe;color:#1e40af;padding:12px 18px;border-radius:18px;margin-bottom:12px;max-width:75%;text-align:center;font-weight:600;">${selectedLang === 'en' ? '🤔 Thinking...' : '🤔 सोच रहा हूँ...'}</div>`;
    messages.scrollTop = messages.scrollHeight;
    
    try {
      const res = await fetch(textApiUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query, language: selectedLang})
      });
      
      const data = await res.json();
      document.getElementById('thinking').remove();
      
      const audioId = 'audio_' + Date.now();
      let msgHTML = `<div style="background:#f3f4f6;color:#1f2937;padding:12px 18px;border-radius:18px;margin-bottom:12px;max-width:75%;font-size:14px;line-height:1.6;">${data.answer}`;
      msgHTML += `<br><button class="widget-listen-btn" id="${audioId}" onclick="fetchWidgetAudio(this, '${selectedLang}')" style="background:#4caf50;color:white;border:none;padding:6px 12px;border-radius:15px;cursor:pointer;font-size:12px;margin-top:8px;transition:all 0.3s;">🔊 सुनें</button>`;
      msgHTML += `</div>`;
      messages.innerHTML += msgHTML;
      messages.scrollTop = messages.scrollHeight;
      
      if(autoPlayAudio){
        setTimeout(() => {
          const listenBtn = document.getElementById(audioId);
          if(listenBtn) listenBtn.click();
        }, 100);
      }
    } catch (e) {
      document.getElementById('thinking')?.remove();
      messages.innerHTML += `<div style="background:#fee2e2;color:#991b1b;padding:12px 18px;border-radius:18px;margin-bottom:12px;font-weight:600;">❌ Error: ${e.message}</div>`;
    }
  }
  
  send.onclick = sendMessage;
  
  window.fetchWidgetAudio = async function(btnElement, language){
    const stopBtn = document.getElementById('ai-saathi-stop');
    let currentAudio = window.aiSaathiAudio;
    
    if(currentAudio && !currentAudio.paused){
      currentAudio.pause();
      currentAudio.currentTime = 0;
      window.aiSaathiAudio = null;
      if(stopBtn) stopBtn.style.display = 'none';
      document.querySelectorAll('.widget-listen-btn').forEach(btn => {
        btn.innerHTML = '🔊 सुनें';
        btn.style.background = '#4caf50';
        btn.disabled = false;
      });
      return;
    }
    
    // Get text from the message div
    const messageDiv = btnElement.closest('div');
    const text = messageDiv.textContent.replace(/🔊 सुनें/g, '').trim();
    
    btnElement.innerHTML = '⏳ Loading...';
    btnElement.disabled = true;
    
    try{
      const res = await fetch(audioApiUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text: text, language: language})
      });
      
      if(!res.ok) throw new Error("Audio API error");
      const data = await res.json();
      
      if(data.audio){
        if(currentAudio){
          currentAudio.pause();
          currentAudio.currentTime = 0;
        }
        
        currentAudio = new Audio('data:audio/mp3;base64,' + data.audio);
        window.aiSaathiAudio = currentAudio;
        if(stopBtn) stopBtn.style.display = 'block';
        
        document.querySelectorAll('.widget-listen-btn').forEach(btn => {
          btn.innerHTML = '🔊 सुनें';
          btn.style.background = '#4caf50';
          btn.disabled = false;
        });
        btnElement.innerHTML = '⏸️ रोकें';
        btnElement.style.background = '#ef4444';
        
        currentAudio.play();
        currentAudio.onended = () => {
          if(stopBtn) stopBtn.style.display = 'none';
          window.aiSaathiAudio = null;
          btnElement.innerHTML = '🔊 सुनें';
          btnElement.style.background = '#4caf50';
        };
      }
    }catch(e){
      btnElement.innerHTML = '❌ Error';
      setTimeout(() => {
        btnElement.innerHTML = '🔊 सुनें';
        btnElement.disabled = false;
      }, 2000);
    }
  };
})();
