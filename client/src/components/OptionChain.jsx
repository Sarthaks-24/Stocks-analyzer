import React, { useMemo } from 'react';
import { AgGridReact } from 'ag-grid-react';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

const OptionChain = ({ data }) => {

    const columnDefs = useMemo(() => [
        {
            headerName: "CALLS",
            children: [
                { field: 'ce_oi', headerName: 'OI', width: 80 },
                { field: 'ce_oi_chg', headerName: 'Chg', width: 70, cellClass: params => params.value > 0 ? 'positive' : 'negative' },
                { field: 'ce_ltp', headerName: 'LTP', width: 80, cellStyle: { fontWeight: 'bold' } },
            ]
        },
        { field: 'strike', headerName: 'Strike', width: 90, pinned: 'left', cellStyle: { textAlign: 'center', backgroundColor: '#334155', fontWeight: 'bold' } },
        {
            headerName: "PUTS",
            children: [
                { field: 'pe_ltp', headerName: 'LTP', width: 80, cellStyle: { fontWeight: 'bold' } },
                { field: 'pe_oi_chg', headerName: 'Chg', width: 70, cellClass: params => params.value > 0 ? 'positive' : 'negative' },
                { field: 'pe_oi', headerName: 'OI', width: 80 },
            ]
        }
    ], []);

    const defaultColDef = useMemo(() => ({
        sortable: true,
        filter: true,
        resizable: true,
        cellStyle: { display: 'flex', alignItems: 'center' }
    }), []);

    return (
        <div className="ag-theme-alpine-dark" style={{ height: '100%', width: '100%' }}>
            <AgGridReact
                rowData={data}
                columnDefs={columnDefs}
                defaultColDef={defaultColDef}
                animateRows={true}
                rowHeight={35}
                headerHeight={40}
            />
        </div>
    );
};

export default OptionChain;
