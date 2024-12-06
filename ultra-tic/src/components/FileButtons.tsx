export default function FileButtons() {
    return (
      <div className="grid grid-rows-2 p-3 mt-5 border rounded border-solid border-1 border-sky-500">
        <div className="row-auto pb-3 ">
            wizexercise.txt
        </div>
        <div className="row-auto space-x-4">
            {/* View Button */}
            <a
            href="/wizexercise.txt"
            target="_blank"
            rel="noopener noreferrer"
            className="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded"
            >
            View File
            </a>
    
            {/* Download Button */}
            <a
            href="/wizexercise.txt"
            download
            className="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded"
            >
            Download File
            </a>
        </div>
      </div>
    );
  }
  