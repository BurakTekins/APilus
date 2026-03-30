import { useState, useEffect, useRef } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function App() {
  const [sessions, setSessions] = useState(() => {
    const saved = localStorage.getItem('acu_chat_sessions');
    return saved ? JSON.parse(saved) : [];
  });
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('acu_chat_dark_mode');
    return saved === 'true' || window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('acu_chat_dark_mode', darkMode);
  }, [darkMode]);

  useEffect(() => {
    localStorage.setItem('acu_chat_sessions', JSON.stringify(sessions));
  }, [sessions]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [sessions, currentSessionId, isLoading, error]);

  const currentSession = sessions.find(s => s.session_id === currentSessionId) || { messages: [] };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const questionText = input.trim();
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'; // Reset height
    }
    setError(null);

    // Optimistically update UI
    const tempUserMessage = { role: 'user', content: questionText };
    let activeSessionId = currentSessionId;
    let tempSessions = [...sessions];
    
    if (!activeSessionId) {
      activeSessionId = 'temp-' + Date.now();
      const newSession = {
        session_id: activeSessionId,
        title: questionText.substring(0, 30) + (questionText.length > 30 ? '...' : ''),
        messages: [tempUserMessage],
        isTemp: true
      };
      tempSessions = [newSession, ...tempSessions];
      setCurrentSessionId(activeSessionId);
    } else {
      tempSessions = tempSessions.map(session => 
        session.session_id === activeSessionId
          ? { ...session, messages: [...session.messages, tempUserMessage] }
          : session
      );
    }
    setSessions(tempSessions);
    setIsLoading(true);

    try {
      const payloadSessionId = activeSessionId.startsWith('temp-') ? null : activeSessionId;
      
      const res = await fetch(`${API_BASE_URL}/api/v1/chat/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: payloadSessionId, question: questionText })
      });

      if (!res.ok) {
        throw new Error('Response error from server');
      }

      const data = await res.json();
      
      setSessions(prevSessions => prevSessions.map(session => {
        if (session.session_id === activeSessionId) {
          const filteredMessages = session.messages.filter(m => m !== tempUserMessage);
          return {
            ...session,
            session_id: data.session_id || session.session_id,
            isTemp: false,
            messages: [
              ...filteredMessages,
              data.user_message || { role: 'user', content: questionText },
              data.assistant_message || { role: 'assistant', content: 'Unknown response' }
            ]
          };
        }
        return session;
      }));
      
      if (!payloadSessionId) {
        setCurrentSessionId(data.session_id);
      }
      
    } catch (err) {
      console.error(err);
      setError("Failed to fetch response. Please check if the backend is running.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e) => {
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 112) + 'px'; 
    setInput(e.target.value);
  };

  return (
    <div className="flex h-screen bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 font-sans antialiased transition-colors duration-200">
      {/* Sidebar */}
      <div className="w-64 bg-zinc-50 dark:bg-zinc-900 border-r border-zinc-200 dark:border-zinc-800 flex flex-col shrink-0 transition-colors">
        <div className="p-4 border-b border-zinc-200 dark:border-zinc-800">
          <button
            onClick={() => setCurrentSessionId(null)}
            className="w-full bg-zinc-900 hover:bg-zinc-800 text-white dark:bg-zinc-100 dark:hover:bg-zinc-200 dark:text-zinc-900 rounded-md py-2 px-4 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-zinc-900 dark:focus:ring-zinc-100 focus:ring-offset-2 dark:focus:ring-offset-zinc-900"
          >
            + New Chat
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {sessions.map(session => (
            <button
              key={session.session_id}
              onClick={() => setCurrentSessionId(session.session_id)}
              className={`w-full text-left px-3 py-2 rounded-md truncate text-sm transition-colors focus:outline-none ${
                currentSessionId === session.session_id
                  ? 'bg-zinc-200 dark:bg-zinc-800 font-medium'
                  : 'hover:bg-zinc-200/50 dark:hover:bg-zinc-800/50 text-zinc-600 dark:text-zinc-400'
              }`}
            >
              {session.title || 'Ongoing Chat'}
            </button>
          ))}
          {sessions.length === 0 && (
            <p className="text-xs text-center text-zinc-500 mt-4">No recent chats</p>
          )}
        </div>

        <div className="p-4 border-t border-zinc-200 dark:border-zinc-800">
          <button
            onClick={() => setDarkMode(!darkMode)}
            className="flex items-center w-full justify-center space-x-2 py-2 rounded-md bg-transparent border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors text-sm focus:outline-none"
          >
            <span>{darkMode ? 'Light Mode' : 'Dark Mode'}</span>
          </button>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 h-full">
        {/* Header */}
        <header className="h-14 shrink-0 border-b border-zinc-200 dark:border-zinc-800 flex items-center px-6 transition-colors">
          <h1 className="text-sm font-semibold tracking-wide">ACU Chatbot</h1>
        </header>

        {/* Messages List */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 bg-white dark:bg-zinc-950">
          {currentSession.messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-zinc-400 dark:text-zinc-600 space-y-4">
              <p className="text-sm font-medium">Start a conversation to see it here.</p>
            </div>
          ) : (
            currentSession.messages.map((msg, idx) => {
              const isUser = msg.role === 'user';
              return (
                <div key={idx} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[85%] sm:max-w-[75%] rounded-2xl px-5 py-3 text-[15px] ${
                      isUser
                        ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 rounded-br-sm'
                        : 'bg-zinc-100 dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 rounded-bl-sm'
                    }`}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">
                      {msg.content}
                    </p>
                  </div>
                </div>
              );
            })
          )}

          {/* Typing Indicator */}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-zinc-100 dark:bg-zinc-900 rounded-2xl rounded-bl-sm px-5 py-4 flex items-center space-x-1.5">
                <div className="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                <div className="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                <div className="w-1.5 h-1.5 bg-zinc-400 rounded-full animate-bounce"></div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} className="h-1" />
        </div>

        {/* Input Area */}
        <div className="shrink-0 p-4 transition-colors">
          <div className="max-w-4xl mx-auto">
            {error && (
              <div className="mb-3 px-4 py-2 bg-red-50 dark:bg-red-950 text-red-600 dark:text-red-400 rounded-md text-sm flex items-center justify-between">
                <span>{error}</span>
                <button onClick={() => setError(null)} className="hover:text-red-800 font-bold ml-2">&times;</button>
              </div>
            )}
            
            <div className="relative flex items-end rounded-xl bg-zinc-100 dark:bg-zinc-900 overflow-hidden focus-within:ring-1 focus-within:ring-zinc-300 dark:focus-within:ring-zinc-700 transition-all">
              <textarea
                ref={textareaRef}
                className="w-full max-h-32 min-h-[52px] py-3.5 pl-4 pr-12 bg-transparent border-none focus:ring-0 resize-none outline-none text-[15px]"
                placeholder="Message..."
                value={input}
                onChange={handleInput}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                rows={1}
                style={{ height: '52px' }}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                className="absolute right-2.5 bottom-2 p-1.5 rounded-lg text-white dark:text-zinc-900 bg-zinc-900 dark:bg-zinc-100 hover:bg-zinc-800 dark:hover:bg-white disabled:bg-zinc-300 dark:disabled:bg-zinc-800 disabled:text-zinc-500 transition-colors focus:outline-none"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
                  <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
                </svg>
              </button>
            </div>
            <div className="text-center mt-2.5 text-xs text-zinc-400 dark:text-zinc-500">
              Press Enter to send, Shift + Enter for new line
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
