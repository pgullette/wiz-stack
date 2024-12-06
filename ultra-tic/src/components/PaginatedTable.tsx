'use client';

import React, { useState, useEffect } from 'react';
import { fetchStats } from '@/app/modal-actions';
import Circle from './icons/Circle';
import Cross from './icons/Cross';

// Define the row type based on the Prisma model
interface Row {
  id: Number;
  username: string;
  createdAt: Date;
  move_count: Number;
  wonAt: Date;
  winner: Number;
}

export default function PaginatedTable() {
  const [rows, setRows] = useState<Row[]>([]);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [liveRefresh, setLiveRefresh] = useState<boolean>(true);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(true);

  const loadPage = async (page: number) => {
    setIsLoading(true);
    const data = await fetchStats(page);
    setRows(data.rows);
    setCurrentPage(data.currentPage);
    setTotalPages(data.totalPages);
    setIsLoading(false);
  };

  useEffect(() => {
    loadPage(currentPage); // Initial load

    let interval: NodeJS.Timeout | undefined;
    if (liveRefresh) {
      interval = setInterval(() => loadPage(currentPage), 5000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [liveRefresh, currentPage]);

  // Handle page change
  const goToNextPage = () => {
    if (currentPage < totalPages) {
      const nextPage = currentPage + 1;
      setCurrentPage(nextPage); // Update currentPage
      loadPage(nextPage); // Fetch new data for the next page
    }
  };

  const goToPreviousPage = () => {
    if (currentPage > 1) {
      const prevPage = currentPage - 1;
      setCurrentPage(prevPage); // Update currentPage
      loadPage(prevPage); // Fetch new data for the previous page
    }
  };

  return (
    <div className="p-4">
        <h1 
          className="text-lg font-bold cursor-pointer" 
          onClick={() => setIsCollapsed(!isCollapsed)} 
        >
          {isCollapsed ? 'Show Stats' : 'Player Stats'}
        </h1>

        {!isCollapsed && (
            <div>
                <div className="mb-4 flex justify-between">
                    <button
                    className="bg-blue-500 text-white px-4 py-2 rounded"
                    onClick={() => loadPage(currentPage)}
                    disabled={isLoading}
                    >
                    {isLoading ? 'Loading...' : 'Refresh'}
                    </button>

                    <label className="flex items-center space-x-2">
                    <input
                        type="checkbox"
                        checked={liveRefresh}
                        onChange={() => setLiveRefresh(!liveRefresh)}
                    />
                    <span>Enable Live Refresh</span>
                    </label>
                </div>

                <table className="w-full border-collapse border border-gray-300">
                    <thead>
                    <tr className="bg-gray-100">
                        <th className="border border-gray-300 p-2">Game</th>
                        <th className="border border-gray-300 p-2">Player</th>
                        <th className="border border-gray-300 p-2">Game Started</th>
                        <th className="border border-gray-300 p-2">Game Won</th>
                        <th className="border border-gray-300 p-2">Move Count</th>
                        <th className="border border-gray-300 p-2">Winner</th>
                    </tr>
                    </thead>
                    <tbody>
                    {rows.map((row) => (
                        <tr key={row.id.toString()}>
                        <td className="border border-gray-300 p-2">{row.id.toString()}</td>
                        <td className="border border-gray-300 p-2">{row.username}</td>
                        <td className="border border-gray-300 p-2">{new Date(row.createdAt).toLocaleString()}</td>
                        <td className="border border-gray-300 p-2">
                            {row.wonAt !== null ?
                                new Date(row.wonAt).toLocaleString() :
                                ""
                            }
                        </td>
                        <td className="border border-gray-300 p-2">{row.move_count.toString()}</td>
                        <td className="border border-gray-300 p-2 w-3 h-3">
                            {row.winner === 2 ?
                                <Circle size={"small"} /> : row.winner == 1 ?
                                <Cross size={"small"} /> : ""
                            }
                        </td>
                        </tr>
                    ))}
                    </tbody>
                </table>

                <div className="mt-4 flex justify-between items-center">
                    <button
                    className="bg-gray-500 text-white px-4 py-2 rounded"
                    onClick={goToPreviousPage}
                    disabled={currentPage === 1}
                    >
                    Previous
                    </button>
                    <span>
                    Page {currentPage} of {totalPages}
                    </span>
                    <button
                    className="bg-gray-500 text-white px-4 py-2 rounded"
                    onClick={goToNextPage}
                    disabled={currentPage === totalPages}
                    >
                    Next
                    </button>
                </div>
        </div>
      )}
    </div>
  );
}