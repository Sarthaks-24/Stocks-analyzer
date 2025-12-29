import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import OptionChain from './components/OptionChain';
import InstrumentSearch from './components/InstrumentSearch';
import { createChart } from 'lightweight-charts';

function App() {
  const [data, setData] = useState([]);
  const [status, setStatus] = useState("Disconnected");
  const ws = useRef(null);

  // No initial mock data, waiting for WebSocket
  // useEffect(() => { ... });

  // WebSocket Connection
  useEffect(() => {
    // ws.current = new WebSocket("ws://localhost:8000/ws/live");
    // ws.current.onopen = () => setStatus("Connected");
    // ws.current.onclose = () => setStatus("Disconnected");
    // ws.current.onmessage = (event) => {
    //    // Handle incoming ticks
    // };
    // return () => ws.current?.close();
  }, []);

  return (
    <div className="dashboard-container">
      <header className="header">
        <div className="title">XTS Pro Terminal</div>
        <div className="controls">
          <select className="control-input">
            <option>NIFTY</option>
            <option>BANKNIFTY</option>
          </select>
          <input type="date" className="control-input" />
        </div>
        <div style={{ marginLeft: 'auto', color: status === 'Connected' ? '#10b981' : '#94a3b8' }}>
          ● {status}
        </div>
      </header>

      <main className="main-content">
        <div className="grid-panel">
          {/* Search Overlay */}
          <InstrumentSearch onAdd={(item) => {
            console.log("Adding", item);
            // Call backend to add to watchlist
            fetch('http://localhost:8000/watchlist/', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(item)
            }).then(res => res.json()).then(data => alert(data.message));
          }} />
          <OptionChain data={data} />
        </div>
        {/* Placeholder for Chart Panel */}
        <div className="chart-panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#475569' }}>
          Select a Strike to View Chart
        </div>
      </main>
    </div>
  );
}

export default App;
