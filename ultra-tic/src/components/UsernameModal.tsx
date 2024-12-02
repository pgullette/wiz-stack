import React from 'react';
import { cookies } from 'next/headers';
import { setUsername, clearUsername } from '@/app/modal-actions';

export default function UsernameModal() {
  // Server-side cookie retrieval
  const session = cookies().get('myapp_session')?.value;

  // If session exists, show welcome screen
  if (session) {
    return (
      <div className="flex flex-col items-center justify-center p-6 bg-green-50 rounded-lg shadow-md max-w-md mx-auto mt-10">
        <h2 className="text-2xl font-bold text-green-800 mb-4">
          Welcome, {JSON.parse(session).username} at {JSON.parse(session).ip}!
        </h2>
        <form action={clearUsername} className="w-full">
          <button 
            type="submit"
            className="w-full bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-4 rounded transition-colors duration-300"
          >
            Logout
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
        <h2 className="text-2xl font-semibold text-gray-800 mb-6 text-center">
          Enter Your Username
        </h2>
        
        <form action={setUsername} className="space-y-4">
          <div className="space-y-2">
            <label 
              htmlFor="username" 
              className="block text-sm font-medium text-gray-700"
            >
              Username
            </label>
            <input
              id="username"
              name="username"
              type="text"
              required
              minLength={2}
              placeholder="Enter your username"
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          
          <button 
            type="submit" 
            className="w-full bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded transition-colors duration-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50"
          >
            Login
          </button>
        </form>
      </div>
    </div>
  );
}