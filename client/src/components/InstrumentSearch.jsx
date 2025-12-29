import React, { useState } from 'react';
import './InstrumentSearch.css';

const InstrumentSearch = ({ onAdd }) => {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);

    // Implement debounce later if needed, for now manual search or enter
    const handleSearch = async () => {
        if (!query) return;
        setLoading(true);
        try {
            // NOTE: Using a hardcoded list for demo if real API fails, 
            // or we can try to hit the real backend if credentials are set.
            const response = await fetch(`http://localhost:8000/search/instruments?searchString=${query}`);
            const data = await response.json();

            // XTS Search response format needs to be handled.
            // Assuming simple list or success wrapper. 
            // Docs said: { type: "success", result: [...] }
            if (data.type === 'success' && data.result) {
                setResults(data.result);
            } else if (Array.isArray(data)) {
                setResults(data);
            } else {
                // Fallback/Mock for UI Testing if backend fails or no auth
                setResults([
                    { instrument_key: "NSE_EQ|INE002A01018", name: "RELIANCE", exchange: "NSE", segment: "NSECM" },
                    { instrument_key: "NSE_EQ|INE009A01021", name: "INFY", exchange: "NSE", segment: "NSECM" }
                ].filter(i => i.name.toLowerCase().includes(query.toLowerCase())));
            }
        } catch (e) {
            console.error("Search failed", e);
            // Mock data on error
            setResults([
                { instrument_key: "NSE_EQ|INE002A01018", name: "RELIANCE", exchange: "NSE", segment: "NSECM" },
                { instrument_key: "NSE_EQ|INE009A01021", name: "INFY", exchange: "NSE", segment: "NSECM" }
            ].filter(i => i.name.toLowerCase().includes(query.toLowerCase())));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="search-container">
            <div className="search-bar">
                <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search items (e.g. RELIANCE)..."
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                />
                <button onClick={handleSearch} disabled={loading}>
                    {loading ? '...' : 'Search'}
                </button>
            </div>

            {results.length > 0 && (
                <div className="results-list">
                    {results.map((item) => (
                        <div key={item.instrument_key} className="result-item">
                            <div className="item-info">
                                <span className="item-name">{item.name}</span>
                                <span className="item-meta">{item.exchange} | {item.segment}</span>
                            </div>
                            <button onClick={() => onAdd(item)} className="add-btn">+</button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default InstrumentSearch;
