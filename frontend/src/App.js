// Hauptkomponente der Aufgabenplaner-App
// Importiert FullCalendar und Plugins für Kalenderfunktionen
// Importiert React-Hooks, CSS und das Logo

import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import { useEffect, useState, useRef } from 'react';

import './App.css';
import LogoPlaner from './logo-planer.svg';
import Login from './Login';
import Register from './Register';
import { jwtDecode } from './jwt-decode';
import { API_BASE } from './config';

// Mapping Hex -> Name für Backend
const HEX_TO_COLORNAME = {
  '#3b82f6': 'blau', // Neu: Kräftiges Blau
  '#6fa8dc': 'blau', // Alt: Soft
  '#3788d8': 'blau', // Alt: Original
  '#ef4444': 'rot', // Neu: Kräftiges Rot
  '#e06666': 'rot', // Alt: Soft
  '#ffb2b2': 'rot', // Alt: Original
  '#b2ffb2': 'grün',
  '#eab308': 'gelb', // Neu: Kräftiges Gelb
  '#ffd966': 'gelb', // Alt: Soft
  '#FFD700': 'gelb', // Alt: Gold
  '#f59e0b': 'gelb', // Alt: Orange
  '#ffe9b2': 'gelb', // Alt: Hell
};
function hexToColorName(hex) {
  return HEX_TO_COLORNAME[hex] || hex;
}
// Mapping Name -> Hex für FullCalendar
const COLORNAME_TO_HEX = {
  'blau': '#3b82f6',
  'rot': '#ef4444',
  'grün': '#b2ffb2',
  'gelb': '#eab308',
  '#3788d8': '#3b82f6', // Fix: Altes Blau auf neues Blau
  '#6fa8dc': '#3b82f6', // Fix: Soft Blau auf neues Blau
  '#ffb2b2': '#ef4444', // Fix: Altes Rot auf neues Rot
  '#e06666': '#ef4444', // Fix: Soft Rot auf neues Rot
  '#FFD700': '#eab308', // Fix: Altes Gold auf neues Gelb
  '#ffd966': '#eab308', // Fix: Soft Gelb auf neues Gelb
  '#f59e0b': '#eab308',
  '#ffe9b2': '#eab308',
};
function colorNameToHex(name) {
  return COLORNAME_TO_HEX[name] || name;
}


function getEmailFromToken(token) {
  try {
    const decoded = jwtDecode(token);
    return decoded.email || decoded.sub || decoded.username || '';
  } catch {
    return '';
  }
}

function App() {
  // Auth-Status
  const [token, setToken] = useState(() => localStorage.getItem('access_token'));
  const [showRegister, setShowRegister] = useState(false);
  // State für alle Aufgaben/Events im Kalender
  const [events, setEvents] = useState([]);
  // State für aktuell ausgewähltes Event (für Details/Bearbeiten)
  const [selectedEvent, setSelectedEvent] = useState(null);
  // State für das Event, das gerade bearbeitet wird
  const [editEvent, setEditEvent] = useState(null);
  // State für Filtereinstellungen (Priorität, Status, Suche)
  const [filters, setFilters] = useState({ priority: '', done: '', search: '' });
  // State für Sichtbarkeit des Chatfensters
  const [chatOpen, setChatOpen] = useState(false);
  // State für Chatnachrichten
  const [chatMessages, setChatMessages] = useState([
    { sender: 'gpt', text: 'Hallo! Ich bin dein intelligenter Assistent. Ich kann Termine eintragen, aus deinen Gewohnheiten lernen und freie Zeitfenster für dich finden. Sag einfach: "Trage Klavier am Freitag um 16 Uhr ein" oder "Wann habe ich Zeit für Sport?"' }
  ]);
  // conversation id to continue thread (persist in localStorage)
  const [conversationId, setConversationId] = useState(() => localStorage.getItem('conversation_id') || null);
  // State für Eingabefeld im Chat
  const [chatInput, setChatInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef(null);
  // State für laufenden Termin-Dialog
  const [pendingTask, setPendingTask] = useState({ title: '', deadline: '', description: '', step: 0 });
  // State für Sichtbarkeit des Dialogs zum Anlegen eines neuen Termins
  const [showNewDialog, setShowNewDialog] = useState(false);
  // State für die Eingabefelder des neuen Termins
  const [newTask, setNewTask] = useState({
    title: '',
    description: '',
    deadline: '',
    priority: 1,
    recurrence: '',
    color: '#3788d8',
  });
  // State für bereits benachrichtigte Termin-IDs (um Spam zu vermeiden)
  const [notifiedIds, setNotifiedIds] = useState(new Set());
  // State für In-App-Benachrichtigungen (Popup)
  const [inAppNotification, setInAppNotification] = useState(null);
  // State für Benachrichtigungs-Historie & Panel
  const [notifications, setNotifications] = useState([]);
  const [showNotificationPanel, setShowNotificationPanel] = useState(false);

  // API-URLs für Backend (unterscheidet Dev/Prod)
  // Wird nun zentral aus config.js geladen
  const TASKS_URL = (API_BASE || '') + '/tasks';

  // Lädt alle Tasks direkt über /tasks (statt /calendar)
  const loadEvents = async () => {
    if (!token) return;
    // Filter-Parameter ggf. anhängen
    let url = TASKS_URL;
    const params = [];
    if (filters.priority) params.push(`priority=${filters.priority}`);
    if (filters.done) params.push(`done=${filters.done}`);
    if (filters.search) params.push(`search=${encodeURIComponent(filters.search)}`);
    if (params.length) url += '?' + params.join('&');
    const res = await fetch(url, {
      headers: token ? { 'Authorization': 'Bearer ' + token } : {}
    });

    if (res.status === 401) {
      console.warn("Nicht authentifiziert - Logout");
      setToken(null);
      localStorage.removeItem('access_token');
      return;
    }

    if (!res.ok) {
      console.error("Fehler beim Laden der Tasks:", res.status, res.statusText);
      return; 
    }

    const data = await res.json();
    
    // Sicherheitscheck: Ist data wirklich ein Array?
    if (!Array.isArray(data)) {
      console.error("Unerwartetes Format vom Backend (kein Array):", data);
      return;
    }

    // Tasks in FullCalendar-Events umwandeln (inkl. Wiederholung, Farbe etc.)
    const events = [];
    data.forEach(task => {
      if (task.deadline) {
        // Wiederholungen (wie vorher im Backend)
        const colorHex = colorNameToHex(task.color);
        if (task.recurrence) {
          // --- WICHTIG: Wiederholungen EXPANDIEREN (Entweder 5 Jahre oder bis Datum) ---
          let recurrenceEnd = null;
          // Versuchen Enddatum zu parsen aus custom_fields
          try {
             if (task.custom_fields && task.custom_fields.recurrence_end) {
                  recurrenceEnd = new Date(task.custom_fields.recurrence_end);
             }
          } catch(e) {}
          
          let loopCount = 0;
          let maxLoops = 260; // Ca 5 Jahre Weekly, oder <1 Jahr daily. Sicherheitshalber Limit.
          
          for (let i = 0; i < maxLoops; i++) {
            let eventDate = new Date(task.deadline);
            if (task.recurrence === 'daily') eventDate.setDate(eventDate.getDate() + i);
            else if (task.recurrence === 'weekly') eventDate.setDate(eventDate.getDate() + 7 * i);
            else if (task.recurrence === 'monthly') eventDate.setMonth(eventDate.getMonth() + i);

            // ABBRUCHBEDINGUNGEN:
            // 1. Wenn ein Enddatum gesetzt ist und wir drüber sind -> Stop
            if (recurrenceEnd && eventDate > recurrenceEnd) break;
            // 2. Wenn kein Enddatum & Daily -> Max 90 Tage anzeigen
            if (!recurrenceEnd && task.recurrence === 'daily' && i > 90) break;
            // 3. Wenn kein Enddatum & Weekly -> Max 52 Wochen anzeigen (1 Jahr)
            if (!recurrenceEnd && task.recurrence === 'weekly' && i > 52) break;
            // 4. Wenn kein Enddatum & Monthly -> Max 24 Monate anzeigen (2 Jahre)
            if (!recurrenceEnd && task.recurrence === 'monthly' && i > 24) break;

            events.push({
              id: `${task.id}-${i}`,
              title: String(task.title),
              start: eventDate,
              end: eventDate,
              description: task.description,
              project_id: task.project_id,
              priority: task.priority,
              done: task.done,
              backgroundColor: task.done ? '#b2ffb2' : colorHex,
              borderColor: task.done ? '#4caf50' : colorHex,
              textColor: task.done ? '#222' : '#ffffff',
              recurrence: task.recurrence,
              notes: task.notes,
              custom_fields: task.custom_fields,
              attachments: task.attachments,
              extendedProps: { ...task }
            });
          }
        } else {
          events.push({
            id: String(task.id),
            title: String(task.title),
            start: new Date(task.deadline),
            end: new Date(task.deadline),
            description: task.description,
            project_id: task.project_id,
            priority: task.priority,
            done: task.done,
            backgroundColor: task.done ? '#b2ffb2' : colorHex,
            borderColor: task.done ? '#4caf50' : colorHex,
            textColor: task.done ? '#222' : '#ffffff',
            recurrence: task.recurrence,
            notes: task.notes,
            custom_fields: task.custom_fields,
            attachments: task.attachments,
            extendedProps: { ...task }
          });
        }
      }
    });
    setEvents(events);
  };

  // useEffect: Lädt Events immer neu, wenn sich Filter ändern
  useEffect(() => { loadEvents(); }, [filters, token]);

  // useEffect: Prüft jede Minute auf anstehende Termine
  useEffect(() => {
    const checkReminders = () => {
      console.log(`[Timer] Prüfe ${events.length} Events...`);

      const now = new Date();
      events.forEach(event => {
        const start = event.start instanceof Date ? event.start : new Date(event.start);
        const diffMs = start - now;
        const diffMins = diffMs / 60000;

        // --- Alarm 1: Vorwarnung (1-15 Min vorher) ---
        if (diffMins > 0 && diffMins <= 15 && !notifiedIds.has(`${event.id}_pre`)) {
           const timeText = start.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
           const msgBody = `Beginnt um ${timeText} Uhr (in ${Math.ceil(diffMins)} Min.)`;
           triggerNotification(event, msgBody);
           markAsNotified(`${event.id}_pre`);
        }

        // --- Alarm 2: Start (Jetzt) ---
        // Toleranz: 0 bis -5 Minuten (falls man 1 Min zu spät reinschaut)
        if (diffMins <= 0 && diffMins > -5 && !notifiedIds.has(`${event.id}_now`)) {
           triggerNotification(event, "Der Termin beginnt jetzt!");
           markAsNotified(`${event.id}_now`);
        }
      });
    };

    const triggerNotification = (event, msgBody) => {
        const newNoti = {
             id: `${event.id}_${Date.now()}`,
             title: event.title,
             time: msgBody,
             timestamp: new Date()
        };
        // Popup anzeigen + In Historie speichern
        setInAppNotification(newNoti);
        setNotifications(prev => [newNoti, ...prev]);

        // Sound abspielen
        try {
            const audio = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
            audio.play().catch(e => console.log("Audio autoplay blocked"));
        } catch(e) {}
    };

    const markAsNotified = (key) => {
       setNotifiedIds(prev => {
          const newSet = new Set(prev);
          newSet.add(key);
          return newSet;
       });
    };
    
    const interval = setInterval(checkReminders, 10000);
    const timeout = setTimeout(checkReminders, 2000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [events, notifiedIds]);


  // Öffnet Dialog zum Anlegen eines neuen Termins, setzt Defaultwerte
  const handleDateClick = (arg) => {
    setNewTask({
      title: '',
      description: '',
      deadline: arg.dateStr + 'T00:00:00',
      priority: 1,
      recurrence: '',
      color: '#3788d8',
    });
    setShowNewDialog(true);
  };

  // Aktualisiert ein Feld im State für neuen Termin
  const handleNewTaskChange = (field, value) => {
    setNewTask(t => ({ ...t, [field]: value }));
  };

  // Checkbox-Handler für Wiederholung (setzt/leert Wert)
  const handleNewTaskCheckbox = (field, value) => {
    setNewTask(t => ({ ...t, [field]: t[field] === value ? '' : value }));
  };

  // Checkbox-Handler für Priorität (nur eine auswählbar)
  const handleNewTaskPriority = (value) => {
    setNewTask(t => ({ ...t, priority: value }));
  };

  // Speichert neuen Termin im Backend, schließt Dialog, lädt Events neu
  const handleNewTaskSubmit = async (e) => {
    e.preventDefault();
    if (new Date(newTask.deadline) < new Date()) {
      alert('Fehler: Termine können nicht in der Vergangenheit angelegt werden.');
      return;
    }
    const id = Date.now();
    await fetch(TASKS_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': 'Bearer ' + token } : {})
      },
      body: JSON.stringify({
        id,
        title: newTask.title,
        description: newTask.description,
        deadline: newTask.deadline,
        priority: newTask.priority,
        done: false,
        project_id: null,
        recurrence: newTask.recurrence,
        color: hexToColorName(newTask.color),
        custom_fields: newTask.recurrence_end ? { recurrence_end: newTask.recurrence_end } : null
      })
    });
    setShowNewDialog(false);
    loadEvents();
  };

  // Wird aufgerufen, wenn ein Termin im Kalender angeklickt wird (öffnet Details)
  const handleEventClick = (clickInfo) => {
    setSelectedEvent(clickInfo.event);
    setEditEvent(null);
  };

  // Wird aufgerufen, wenn ein Termin per Drag-and-Drop verschoben wird (Datum ändern)
  const handleEventDrop = async (info) => {
    const now = new Date();
    if (info.oldEvent.start > now && info.event.start < now) {
      alert('Fehler: Zukünftige Termine können nicht in die Vergangenheit verschoben werden.');
      info.revert();
      return;
    }
    const id = info.event.id.split('-')[0]; // Für Wiederholungen
    const updates = { deadline: info.event.startStr };
    await fetch(TASKS_URL + '/' + id, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': 'Bearer ' + token } : {})
      },
      body: JSON.stringify(updates)
    });
    loadEvents();
  };

  // Markiert ausgewählten Termin als erledigt (Backend-Update)
  const handleMarkDone = async () => {
    if (!selectedEvent) return;
    const id = selectedEvent.id.split('-')[0];
    await fetch(TASKS_URL + '/' + id + '/done', {
      method: 'POST',
      headers: token ? { 'Authorization': 'Bearer ' + token } : {}
    });
    setSelectedEvent(null);
    loadEvents();
  };

  // Markiert ausgewählten Termin als NICHT erledigt (Backend-Update)
  const handleMarkUndone = async () => {
    if (!selectedEvent) return;
    const id = selectedEvent.id.split('-')[0];
    await fetch(TASKS_URL + '/' + id + '/undone', {
      method: 'POST',
      headers: token ? { 'Authorization': 'Bearer ' + token } : {}
    });
    setSelectedEvent(null);
    loadEvents();
  };

  // Löscht ausgewählten Termin (Backend-Delete)
  const handleDelete = async () => {
    if (!selectedEvent) return;
    const id = selectedEvent.id.split('-')[0];
    await fetch(TASKS_URL + '/' + id, {
      method: 'DELETE',
      headers: token ? { 'Authorization': 'Bearer ' + token } : {}
    });
    setSelectedEvent(null);
    loadEvents();
  };

  // Öffnet Bearbeiten-Dialog für ausgewählten Termin, kopiert Werte in editEvent
  const handleEdit = () => {
    if (!selectedEvent) {
      alert('Fehler: Kein Termin ausgewählt!');
      return;
    }
    // Defensive Kopie und Fallbacks für editEvent
    const ev = selectedEvent;
    setEditEvent({
      ...ev,
      id: ev.id, // explizit setzen
      title: ev.title || '',
      start: ev.startStr || ev.start || '',
      backgroundColor: ev.backgroundColor || '#3788d8',
      extendedProps: {
        ...ev.extendedProps,
        description: ev.extendedProps?.description || '',
        priority: ev.extendedProps?.priority || 1,
        recurrence: ev.extendedProps?.recurrence || '',
        notes: ev.extendedProps?.notes || '',
        custom_fields: ev.extendedProps?.custom_fields || {},
        attachments: ev.extendedProps?.attachments || [],
        done: ev.extendedProps?.done || false,
        project_id: ev.extendedProps?.project_id || null
      }
    });
  };

  // Speichert Änderungen am bearbeiteten Termin im Backend
  const handleEditSave = async (e) => {
    e.preventDefault();
    if (!editEvent || !editEvent.id) {
      alert('Fehler: Kein Termin zum Bearbeiten ausgewählt!');
      return;
    }
    
    // Check: Future -> Past forbidden
    if (selectedEvent) {
      const now = new Date();
      const oldDate = selectedEvent.start instanceof Date ? selectedEvent.start : new Date(selectedEvent.start);
      const newDate = new Date(editEvent.start);
      if (oldDate > now && newDate < now) {
        alert('Fehler: Zukünftige Termine können nicht in die Vergangenheit verschoben werden.');
        return;
      }
    }

    const id = (typeof editEvent.id === 'string' ? editEvent.id : String(editEvent.id)).split('-')[0];
    let deadline = editEvent.start;
    if (deadline instanceof Date) deadline = deadline.toISOString();
    if (typeof deadline === 'object' && deadline.toISOString) deadline = deadline.toISOString();
    await fetch(TASKS_URL + '/' + id, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': 'Bearer ' + token } : {})
      },
      body: JSON.stringify({
        id,
        title: editEvent.title,
        description: editEvent.extendedProps.description,
        deadline: deadline,
        priority: editEvent.extendedProps.priority,
        done: editEvent.extendedProps.done || false,
        project_id: editEvent.extendedProps.project_id || null,
        recurrence: editEvent.extendedProps.recurrence,
        color: hexToColorName(editEvent.backgroundColor)
      })
    });
    setEditEvent(null);
    setSelectedEvent(null);
    loadEvents();
  };

  // Schließt alle Dialoge (Details/Bearbeiten)
  const handleCloseDialog = () => {
    setSelectedEvent(null);
    setEditEvent(null);
  };

  // Aktualisiert Filter-State bei Auswahländerung
  const handleFilterChange = (e) => {
    setFilters(f => ({ ...f, [e.target.name]: e.target.value }));
  };

  // Aktualisiert Such-Filter bei Texteingabe
  const handleSearch = (e) => {
    setFilters(f => ({ ...f, search: e.target.value }));
  };

  // Sprachsteuerung (Speech-to-Text)
  const handleVoiceInput = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Dein Browser unterstützt keine Sprachsteuerung.');
      return;
    }
    
    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'de-DE';
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);

    recognition.onresult = (event) => {
      let newText = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          newText += event.results[i][0].transcript + ' ';
        }
      }
      if (newText.trim()) {
        setChatInput(prev => (prev.trim() ? prev.trim() + ' ' : '') + newText.trim());
      }
    };

    recognition.onerror = (event) => {
      console.error('Spracherkennung Fehler:', event.error);
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
  };

  // KI-gestützter Chat-Handler mit Termin-Dialog
  const handleChatSend = async (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    const userMsg = chatInput;
    setChatMessages(msgs => [...msgs, { sender: 'user', text: userMsg }]);
    setChatInput('');

    // If there's an ongoing pendingTask, forward the user's message to the backend
    // so the LM (qwen) handles follow-up questions and produces assistant replies.
    // We avoid inserting assistant messages locally here to ensure all replies come from LM Studio.

    // Prüfe, ob der Nutzer einen Termin anlegen möchte
    if (/termin|erinnerung|kalender/i.test(userMsg)) {
      setPendingTask({ title: '', deadline: '', description: '', step: 1 });
      // Do not insert a local assistant message here; let the backend (qwen) ask the follow-up.
    }

    // Standard: normale KI-Antwort
    try {
      // disable input while request is inflight to avoid races
      setIsSending(true);

      // Prefer stable value from localStorage (state may lag); fall back to state
      const storedConv = localStorage.getItem('conversation_id');
      const convToUse = storedConv || conversationId || null;
      const body = { prompt: userMsg };
      if (convToUse) body.conversation_id = convToUse;

      const tokenLocal = localStorage.getItem('access_token') || token;
      const headers = { 'Content-Type': 'application/json' };
      if (tokenLocal) headers['Authorization'] = 'Bearer ' + tokenLocal;

      const res = await fetch((API_BASE || '') + '/chat', {
        method: 'POST',
        headers,
        body: JSON.stringify(body)
      });
      if (!res.ok) throw new Error('Fehler vom Server');
      const data = await res.json();
      // persist conversation id immediately and atomically
      if (data.conversation_id) {
        localStorage.setItem('conversation_id', data.conversation_id);
        setConversationId(data.conversation_id);
      }
      setChatMessages(msgs => [...msgs, { sender: 'gpt', text: data.response }]);

      // Always refresh calendar after chat response - a task may have been auto-created
      // even without explicit auto_created_task_id in the response (e.g. on earlier message)
      try {
        await loadEvents();
      } catch (err) {
        console.warn('Could not refresh events after chat', err);
      }

      // Auto-reset conversation after task is confirmed/completed so next task starts fresh
      // Detect confirmation patterns in user message or completion patterns in assistant response
      // REMOVED: User wants to be able to add info to the last task even after confirmation.
      // The conversation will persist until the user manually starts a new topic or the session expires.
      /*
      const userConfirmPattern = /^\s*(ja|jap|ok|okay|nein|fertig|danke|alles klar|passt|gut)\s*$/i;
      const assistantDonePattern = /(alles klar|termin gespeichert|termin steht|eingetragen|fertig|notiert)/i;
      if (userConfirmPattern.test(userMsg) || assistantDonePattern.test(data.response || '')) {
        // Clear conversation so next appointment starts fresh
        localStorage.removeItem('conversation_id');
        setConversationId(null);
      }
      */
    } catch (err) {
      setChatMessages(msgs => [...msgs, { sender: 'gpt', text: 'Fehler beim Abrufen der KI-Antwort.' }]);
    } finally {
      setIsSending(false);
    }
  };

    // Confirmation is now handled via chat replies (e.g. user says "ja").
    // The explicit confirm button and handler have been removed.

  // Login/Registrierung vorschalten
  if (!token) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <h1 className="auth-title">{showRegister ? 'Registrieren' : 'Willkommen zurück'}</h1>
          {showRegister ? (
            <Register onRegister={() => setShowRegister(false)} />
          ) : (
            <Login onLogin={() => { setToken(localStorage.getItem('access_token')); }} />
          )}
          <div className="auth-switch">
            {showRegister ? 'Bereits registriert?' : 'Noch kein Account?'}
            <button onClick={() => setShowRegister(!showRegister)}>
              {showRegister ? 'Zum Login' : 'Registrieren'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Email aus Token extrahieren
  const userEmail = getEmailFromToken(token);

  // Render-Funktion für Events im Kalender (fügt Icon für Wiederholung hinzu)
  const renderEventContent = (eventInfo) => {
    return (
      <div style={{ overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
        {eventInfo.timeText && <span style={{ marginRight: '4px', fontWeight: 'bold' }}>{eventInfo.timeText}</span>}
        <span>{eventInfo.event.title}</span>
        {eventInfo.event.extendedProps.recurrence && (
          <span style={{ marginLeft: '4px', fontWeight: 'bold', fontSize: '1.1em' }} title="Wiederkehrender Termin">↻</span>
        )}
      </div>
    );
  };

  // Render-Teil: Enthält Logo, Filter, Kalender, Dialoge, Chatfenster
  return (
    <div className="App">
      {/* Benutzerkennung immer oben rechts als Overlay, aber nur wenn Token vorhanden */}
      {/* Benutzerkennung entfernt */}
      {/* Kopfzeile mit Logo, Titel und Logout */}
      <header className="app-header">
        <div style={{display: 'flex', alignItems: 'center'}}>
          <img src={LogoPlaner} alt="Logo Aufgabenplaner" className="app-logo" />
          <h1 className="app-title">Intelligenter Aufgabenplaner</h1>
        </div>
        {token && (
          <div style={{ position: 'relative', marginRight: '1rem' }}>
            <button 
               onClick={() => setShowNotificationPanel(!showNotificationPanel)} 
               className="btn-icon"
               title="Benachrichtigungen"
            >
              🔔
               {notifications.length > 0 && (
                  <span className="badge">{notifications.length}</span>
               )}
            </button>
            
            {showNotificationPanel && (
               <div className="notification-panel">
                   <h3>Benachrichtigungen</h3>
                   {notifications.length === 0 ? <p style={{padding: '0.5rem', textAlign: 'center', color: '#888'}}>Keine Nachrichten</p> : (
                      <ul className="notification-list">
                          {notifications.map(n => (
                              <li key={n.id} className="notification-item">
                                  <strong>{n.title}</strong>
                                  <p>{n.time}</p>
                                  <small>{n.timestamp.toLocaleTimeString()}</small>
                              </li>
                          ))}
                      </ul>
                   )}
               </div>
            )}
          </div>
        )}
        {token && (
          <button onClick={() => { localStorage.removeItem('access_token'); setToken(null); }} className="btn-logout">Logout</button>
        )}
      </header>
      <div className="main-content">
        {/* Filterleiste für Priorität, Status, Suche */}
        <div className="filters-bar">
          <div className="filter-group">
            <label>Priorität:</label>
            <select name="priority" value={filters.priority} onChange={handleFilterChange} className="filter-select">
              <option value="">Alle</option>
              <option value="1">Niedrig</option>
              <option value="2">Mittel</option>
              <option value="3">Hoch</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Status:</label>
            <select name="done" value={filters.done} onChange={handleFilterChange} className="filter-select">
              <option value="">Alle</option>
              <option value="false">Offen</option>
              <option value="true">Erledigt</option>
            </select>
          </div>
          <input type="text" placeholder="Suchen..." value={filters.search} onChange={handleSearch} className="search-input" />
        </div>
        {/* FullCalendar-Komponente mit allen Events */}
        <FullCalendar
          plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
          initialView="dayGridMonth"
          events={events}
          height={650}
          dateClick={handleDateClick}
          eventClick={handleEventClick}
          eventDrop={handleEventDrop}
          editable={true}
          selectable={true}
          headerToolbar={{ left: 'prev,next today', center: 'title', right: 'dayGridMonth,timeGridWeek,timeGridDay' }}
          displayEventTime={true} // Uhrzeit wieder anzeigen
          eventDisplay="block" // Termine immer als Block anzeigen (mit Hintergrundfarbe)
          eventContent={renderEventContent}
          eventTimeFormat={{
            hour: '2-digit',
            minute: '2-digit',
            meridiem: false,
            hour12: false
          }}
        />
        {/* Dialog zum Anlegen eines neuen Termins */}
        {showNewDialog && (
          <div className="dialog-overlay">
            <form onSubmit={handleNewTaskSubmit} className="dialog-card">
              <h2>Neuen Termin anlegen</h2>
              <div className="form-group">
                <label>Titel:</label>
                <input value={newTask.title} onChange={e => handleNewTaskChange('title', e.target.value)} required />
              </div>
              <div className="form-group">
                <label>Beschreibung:</label>
                <input value={newTask.description} onChange={e => handleNewTaskChange('description', e.target.value)} />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Datum:</label>
                  <input type="date" value={newTask.deadline ? newTask.deadline.slice(0,10) : ''} onChange={e => handleNewTaskChange('deadline', e.target.value + (newTask.deadline ? newTask.deadline.slice(10) : 'T00:00:00'))} required />
                </div>
                <div className="form-group">
                  <label>Uhrzeit:</label>
                  <input type="time" value={newTask.deadline ? newTask.deadline.slice(11,16) : ''} onChange={e => handleNewTaskChange('deadline', (newTask.deadline ? newTask.deadline.slice(0,10) : '') + 'T' + e.target.value + ':00')} required />
                </div>
              </div>
              
              <div className="form-group">
                <label>Priorität:</label>
                <div className="checkbox-group">
                  <label className="checkbox-label"><input type="checkbox" checked={newTask.priority === 1} onChange={() => handleNewTaskPriority(1)} /> Niedrig</label>
                  <label className="checkbox-label"><input type="checkbox" checked={newTask.priority === 2} onChange={() => handleNewTaskPriority(2)} /> Mittel</label>
                  <label className="checkbox-label"><input type="checkbox" checked={newTask.priority === 3} onChange={() => handleNewTaskPriority(3)} /> Hoch</label>
                </div>
              </div>

              <div className="form-group">
                <label>Wiederholung:</label>
                <div className="checkbox-group">
                  <label className="checkbox-label"><input type="checkbox" checked={newTask.recurrence === ''} onChange={() => handleNewTaskCheckbox('recurrence', '')} /> Keine</label>
                  <label className="checkbox-label"><input type="checkbox" checked={newTask.recurrence === 'daily'} onChange={() => handleNewTaskCheckbox('recurrence', 'daily')} /> Täglich</label>
                  <label className="checkbox-label"><input type="checkbox" checked={newTask.recurrence === 'weekly'} onChange={() => handleNewTaskCheckbox('recurrence', 'weekly')} /> Wöchentlich</label>
                  <label className="checkbox-label"><input type="checkbox" checked={newTask.recurrence === 'monthly'} onChange={() => handleNewTaskCheckbox('recurrence', 'monthly')} /> Monatlich</label>
                </div>
              </div>
              {newTask.recurrence && (
                <div className="form-group">
                  <label>Wiederholung bis (Datum):</label>
                   <input type="date" value={newTask.recurrence_end || ''} onChange={(e) => handleNewTaskChange('recurrence_end', e.target.value)} />
                </div>
              )}

              <div className="form-group">
                <label>Farbe:</label>
                <div className="checkbox-group">
                  <label className="checkbox-label" style={{color: '#3b82f6'}}><input type="checkbox" checked={newTask.color === '#3b82f6'} onChange={() => handleNewTaskChange('color', '#3b82f6')} /> Blau</label>
                  <label className="checkbox-label" style={{color: '#ef4444'}}><input type="checkbox" checked={newTask.color === '#ef4444'} onChange={() => handleNewTaskChange('color', '#ef4444')} /> Rot</label>
                  <label className="checkbox-label" style={{color: '#eab308'}}><input type="checkbox" checked={newTask.color === '#eab308'} onChange={() => handleNewTaskChange('color', '#eab308')} /> Gelb</label>
                </div>
              </div>

              <div className="dialog-actions">
                <button type="submit" className="btn-primary">Speichern</button>
                <button type="button" onClick={() => setShowNewDialog(false)} className="btn-secondary">Abbrechen</button>
              </div>
            </form>
          </div>
        )}
        {/* Dialog für Event-Details (mit Bearbeiten/Löschen/Erledigen) */}
        {selectedEvent && !editEvent && (
          <div className="dialog-overlay">
            <div className="dialog-card">
              <h2>{selectedEvent.title}</h2>
              <div className="event-details">
                <p><b>Beschreibung:</b> {selectedEvent.extendedProps.description || 'Keine Beschreibung'}</p>
                <p><b>Erledigt:</b> {selectedEvent.extendedProps.done ? 'Ja' : 'Nein'}</p>
                <p><b>Priorität:</b> {selectedEvent.extendedProps.priority}</p>
              </div>
              
              <div className="dialog-actions">
                {!selectedEvent.extendedProps.done ? (
                  <button onClick={handleMarkDone} className="btn-primary">✔️ Erledigt</button>
                ) : (
                  <button onClick={handleMarkUndone} className="btn-secondary">↩️ Wiedereröffnen</button>
                )}
                <button onClick={handleEdit} className="btn-secondary">✏️ Bearbeiten</button>
                <button onClick={handleDelete} className="btn-danger">🗑️ Löschen</button>
                <button onClick={handleCloseDialog} className="btn-secondary">Schließen</button>
              </div>
            </div>
          </div>
        )}
        {/* Dialog zum Bearbeiten eines Termins */}
        {editEvent && (
          <div className="dialog-overlay">
            <form onSubmit={handleEditSave} className="dialog-card">
              <h2>Termin bearbeiten</h2>
              <div className="form-group">
                <label>Titel:</label>
                <input value={editEvent.title} onChange={e => setEditEvent(ev => ({...ev, title: e.target.value}))} required />
              </div>
              <div className="form-group">
                <label>Beschreibung:</label>
                <input value={editEvent.extendedProps.description || ''} onChange={e => setEditEvent(ev => ({...ev, extendedProps: {...ev.extendedProps, description: e.target.value}}))} />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Datum:</label>
                  <input type="date" value={editEvent.start ? (typeof editEvent.start === 'string' ? editEvent.start.slice(0,10) : editEvent.start.toISOString().slice(0,10)) : ''} onChange={e => setEditEvent(ev => ({...ev, start: e.target.value + (ev.start ? (typeof ev.start === 'string' ? ev.start.slice(10) : 'T00:00:00') : 'T00:00:00')}))} required />
                </div>
                <div className="form-group">
                  <label>Uhrzeit:</label>
                  <input type="time" value={editEvent.start ? (typeof editEvent.start === 'string' ? editEvent.start.slice(11,16) : editEvent.start.toISOString().slice(11,16)) : ''} onChange={e => setEditEvent(prev => ({...prev, start: (prev.start ? (typeof prev.start === 'string' ? prev.start.slice(0,10) : prev.start.toISOString().slice(0,10)) : '') + 'T' + e.target.value + ':00'}))} required />
                </div>
              </div>

              <div className="form-group">
                <label>Priorität:</label>
                <div className="checkbox-group">
                  <label className="checkbox-label"><input type="checkbox" checked={editEvent.extendedProps.priority === 1} onChange={() => setEditEvent(ev => ({...ev, extendedProps: {...ev.extendedProps, priority: 1}}))}/> Niedrig</label>
                  <label className="checkbox-label"><input type="checkbox" checked={editEvent.extendedProps.priority === 2} onChange={() => setEditEvent(ev => ({...ev, extendedProps: {...ev.extendedProps, priority: 2}}))}/> Mittel</label>
                  <label className="checkbox-label"><input type="checkbox" checked={editEvent.extendedProps.priority === 3} onChange={() => setEditEvent(ev => ({...ev, extendedProps: {...ev.extendedProps, priority: 3}}))}/> Hoch</label>
                </div>
              </div>

              <div className="form-group">
                <label>Wiederholung:</label>
                <div className="checkbox-group">
                  <label className="checkbox-label"><input type="checkbox" checked={editEvent.extendedProps.recurrence === ''} onChange={() => setEditEvent(ev => ({...ev, extendedProps: {...ev.extendedProps, recurrence: ''}}))}/> Keine</label>
                  <label className="checkbox-label"><input type="checkbox" checked={editEvent.extendedProps.recurrence === 'daily'} onChange={() => setEditEvent(ev => ({...ev, extendedProps: {...ev.extendedProps, recurrence: 'daily'}}))}/> Täglich</label>
                  <label className="checkbox-label"><input type="checkbox" checked={editEvent.extendedProps.recurrence === 'weekly'} onChange={() => setEditEvent(ev => ({...ev, extendedProps: {...ev.extendedProps, recurrence: 'weekly'}}))}/> Wöchentlich</label>
                  <label className="checkbox-label"><input type="checkbox" checked={editEvent.extendedProps.recurrence === 'monthly'} onChange={() => setEditEvent(ev => ({...ev, extendedProps: {...ev.extendedProps, recurrence: 'monthly'}}))}/> Monatlich</label>
                </div>
              </div>

              <div className="form-group">
                <label>Farbe:</label>
                <div className="checkbox-group">
                  <label className="checkbox-label" style={{color: '#3b82f6'}}><input type="checkbox" checked={editEvent.backgroundColor === '#3b82f6'} onChange={() => setEditEvent(ev => ({...ev, backgroundColor: '#3b82f6'}))}/> Blau</label>
                  <label className="checkbox-label" style={{color: '#ef4444'}}><input type="checkbox" checked={editEvent.backgroundColor === '#ef4444'} onChange={() => setEditEvent(ev => ({...ev, backgroundColor: '#ef4444'}))}/> Rot</label>
                  <label className="checkbox-label" style={{color: '#eab308'}}><input type="checkbox" checked={editEvent.backgroundColor === '#eab308'} onChange={() => setEditEvent(ev => ({...ev, backgroundColor: '#eab308'}))}/> Gelb</label>
                </div>
              </div>

              <div className="dialog-actions">
                <button type="submit" className="btn-primary">Speichern</button>
                <button type="button" onClick={handleCloseDialog} className="btn-secondary">Abbrechen</button>
              </div>
            </form>
          </div>
        )}

        {/* Chat-Fenster */}
        {chatOpen && (
          <div className="chat-window">
            <div className="chat-header">
                <span>Assistenz</span>
                <small>Online</small>
            </div>
            <div className="chat-messages">
              {chatMessages.map((msg, i) => (
                <div key={i} className={`message ${msg.sender === 'user' ? 'message-user' : 'message-gpt'}`}>
                  {msg.text}
                </div>
              ))}
              {isSending && (
                  <div className="message message-gpt">
                      <div className="typing-indicator">
                          <span></span><span></span><span></span>
                      </div>
                  </div>
              )}
            </div>
            <form onSubmit={handleChatSend} className="chat-input-area">
              <button type="button" onClick={handleVoiceInput} className="chat-mic-btn" title="Spracheingabe">
                {isListening ? '🛑' : '🎤'}
              </button>
              <input
                className="chat-input"
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                placeholder="Frag mich etwas..."
                disabled={isSending}
              />
            </form>
          </div>
        )}

        {/* Button zum Öffnen/Schließen des Chatfensters */}
        <button onClick={() => setChatOpen(o => !o)} className="chat-fab">
          💬
        </button>
        {/* IN-APP BENACHRICHTIGUNG (FALLBACK) */}
        {inAppNotification && (
          <div className="in-app-notification" onClick={() => setInAppNotification(null)}>
            <div className="notification-content">
              <h3>⏰ {inAppNotification.title}</h3>
              <p>{inAppNotification.time}</p>
              <span className="close-hint">(Klicken zum Schließen)</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Exportiert die Hauptkomponente
export default App;
