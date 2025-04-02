"use client";

import { useState, useRef, useEffect, useMemo } from 'react';
import { Document, Page, pdfjs } from 'react-pdf'; // Import react-pdf components
import 'react-pdf/dist/esm/Page/AnnotationLayer.css'; // Default styling for annotation layer
import 'react-pdf/dist/esm/Page/TextLayer.css'; // Default styling for text layer

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

// Configure PDF.js worker
// You might need to copy the worker file to your public directory
// Option 1: Use CDN (easier for setup)
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

// Option 2: If you prefer hosting the worker yourself:
// 1. npm install pdfjs-dist
// 2. Copy node_modules/pdfjs-dist/build/pdf.worker.min.mjs to public/ directory
// 3. Set workerSrc: pdfjs.GlobalWorkerOptions.workerSrc = `/pdf.worker.min.mjs`;

export default function Home() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pdfId, setPdfId] = useState<string | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Chat State
  interface ChatMessage {
    sender: 'user' | 'ai';
    text: string;
  }
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState<string>("");
  const [isSending, setIsSending] = useState<boolean>(false); // To disable input while waiting for AI

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && file.type === "application/pdf") {
      setSelectedFile(file);
      setError(null); // Clear previous errors
      // Automatically start upload after selecting
      handleUpload(file);
    } else {
      setSelectedFile(null);
      setError("Please select a valid PDF file.");
      alert("Please select a valid PDF file."); // Simple feedback
    }
  };

  const handleUploadButtonClick = () => {
    // Trigger click on the hidden file input
    fileInputRef.current?.click();
  };

  const handleUpload = async (fileToUpload: File) => {
    if (!fileToUpload) {
      setError("No file selected.");
      return;
    }

    setUploading(true);
    setError(null);
    setPdfId(null); // Reset pdfId on new upload

    const formData = new FormData();
    formData.append("file", fileToUpload);

    try {
      // Assuming backend runs on port 8000
      const response = await fetch("http://localhost:8000/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ description: "Upload failed with status: " + response.status }));
        throw new Error(errorData.description || "Failed to upload PDF.");
      }

      const result = await response.json();
      setPdfId(result.pdf_id);
      setSelectedFile(null); // Clear selection after successful upload (optional)
      setCurrentPage(1); // Reset to first page on new upload
      setNumPages(null); // Reset page count
      setChatMessages([]); // Clear chat history on new upload
      setError(null); // Clear previous errors
      alert(`PDF '${result.pdf_id}' uploaded successfully!`); // Simple feedback
      // TODO: Trigger loading the PDF viewer with the new pdfId

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "An unknown error occurred during upload.";
      setError(errorMessage);
      console.error("Upload error:", err);
      alert(`Upload failed: ${errorMessage}`); // Simple feedback
    } finally {
      setUploading(false);
    }
  };

  // react-pdf functions
  function onDocumentLoadSuccess({ numPages: nextNumPages }: { numPages: number }){
    setNumPages(nextNumPages);
  }

  function onDocumentLoadError(loadError: Error) {
    console.error("Failed to load PDF:", loadError);
    setError(`Failed to load PDF: ${loadError.message}`);
    setPdfId(null); // Clear pdfId if loading fails
    setNumPages(null); // Clear numPages as well
  }

  const goToPrevPage = () => setCurrentPage(prev => (prev > 1 ? prev - 1 : prev));
  const goToNextPage = () => setCurrentPage(prev => (numPages && prev < numPages ? prev + 1 : prev));

  useEffect(() => {
    console.log("Component Render - pdfId:", pdfId, "currentPage:", currentPage, "numPages:", numPages);
  });

  // Memoize options for react-pdf Document component
  // Prevents unnecessary re-renders due to options object changing identity
  const pdfDocumentOptions = useMemo(() => ({
    // Add any specific pdfjs worker options here if needed in the future
    // For now, we mainly need this to provide a stable object reference.
  }), []);

  const handleSendMessage = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!chatInput.trim() || !pdfId || isSending) return;

    const userMessage: ChatMessage = { sender: 'user', text: chatInput };
    setChatMessages((prev) => [...prev, userMessage]);
    setChatInput("");
    setIsSending(true);
    setError(null); // Clear previous errors

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ pdf_id: pdfId, query: userMessage.text }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.description || `HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      const aiMessage: ChatMessage = { sender: 'ai', text: result.answer };
      setChatMessages((prev) => [...prev, aiMessage]);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "An unknown error occurred.";
      console.error("Chat Error:", err);
      const errorResponseMessage: ChatMessage = {
        sender: 'ai',
        text: `Sorry, I encountered an error: ${errorMessage}`,
      };
      setChatMessages((prev) => [...prev, errorResponseMessage]);
      setError(`Chat failed: ${errorMessage}`); // Also show error maybe elsewhere
    } finally {
      setIsSending(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-4 md:p-8 lg:p-12 bg-muted/40">
      <div className="w-full max-w-7xl grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* PDF Viewer Section (Left/Main) */}
        <div className="lg:col-span-2">
          <Card className="h-[85vh] flex flex-col">
            <CardHeader>
              <CardTitle>PDF Viewer</CardTitle>
              <CardDescription>
                {pdfId ? `Viewing: ${pdfId} (Page ${currentPage} of ${numPages || '?'})` : "Upload a PDF to start reading."}
              </CardDescription>
            </CardHeader>
            {/* Make CardContent scrollable and contain the Document */}
            <CardContent className="flex-grow bg-gray-200 dark:bg-gray-800 rounded-md flex items-center justify-center overflow-auto p-2">
              {pdfId ? (
                <>
                  {console.log("Rendering Document component for pdfId:", pdfId)}
                  <Document
                    file={pdfId ? `http://localhost:8000/pdf/${pdfId}/raw` : null} // Pass null if no pdfId
                    onLoadSuccess={onDocumentLoadSuccess}
                    onLoadError={(error) => {
                      console.error("PDF Load Error:", error);
                      setError(`Failed to load PDF: ${error.message}`);
                    }}
                    className="flex justify-center"
                    options={pdfDocumentOptions} // Use memoized options
                  >
                    <Page
                      key={`page_${currentPage}`}
                      pageNumber={currentPage}
                      renderTextLayer={true} // Enable text selection/copy
                      renderAnnotationLayer={true} // Display annotations/links
                      width={800} // Adjust width as needed, or make responsive
                      className="max-w-full h-auto drop-shadow-lg"
                    />
                  </Document>
                </>
              ) : (
                <p className="text-muted-foreground">Loading PDF...</p>
              )}
            </CardContent>
            <CardFooter className="flex justify-between items-center pt-4 flex-wrap gap-2">
              {/* Hidden file input */}
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept="application/pdf"
                style={{ display: 'none' }} // Hide the default input
              />
              {/* Visible Upload Button */}
              <Button onClick={handleUploadButtonClick} disabled={uploading}>
                {uploading ? "Uploading..." : pdfId ? `Uploaded: ${pdfId}` : "Upload PDF"}
              </Button>
              {/* Pagination Controls (only show if PDF is loaded) */}
              {pdfId && numPages && (
                <div className="flex items-center space-x-2">
                  <Button variant="outline" onClick={goToPrevPage} disabled={currentPage <= 1}>
                    Previous
                  </Button>
                  <span>
                    Page {currentPage} of {numPages}
                  </span>
                  <Button variant="outline" onClick={goToNextPage} disabled={currentPage >= numPages}>
                    Next
                  </Button>
                </div>
              )}
              {/* Placeholder for search input/button */}
              <div className="flex space-x-2">
                <Input placeholder="Search in PDF..." className="w-auto"/>
                <Button>Search</Button>
              </div>
            </CardFooter>
          </Card>
        </div>

        {/* Chat Section (Right) */}
        <div className="lg:col-span-1">
          <Card className="h-[85vh] flex flex-col">
            <CardHeader>
              <CardTitle>Chat Assistant</CardTitle>
              <CardDescription>
                {pdfId ? `Ask questions about: ${pdfId}` : "Upload a PDF to enable chat."}
              </CardDescription>
            </CardHeader>
            {/* Chat Message Display Area */}
            <CardContent className="flex-grow overflow-y-auto p-4 space-y-4 bg-muted/50">
              {chatMessages.length === 0 && (
                 <p className="text-center text-muted-foreground text-sm">
                    {pdfId ? "Chat history is empty. Ask a question below!" : "No PDF uploaded."}
                </p>
              )}
              {chatMessages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[75%] rounded-lg px-4 py-2 text-sm ${message.sender === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-secondary text-secondary-foreground'
                      }`}
                  >
                    {message.text}
                  </div>
                </div>
              ))}
               {isSending && (
                 <div className="flex justify-start">
                   <div className="max-w-[75%] rounded-lg px-4 py-2 text-sm bg-secondary text-secondary-foreground animate-pulse">
                     Thinking...
                   </div>
                 </div>
               )} 
              {/* TODO: Add Scroll anchoring - scroll to bottom on new message */}
            </CardContent>
            {/* Chat Input Area */}
            <CardFooter className="p-4 border-t">
              <form onSubmit={handleSendMessage} className="flex w-full items-center space-x-2">
                <Input
                  placeholder={pdfId ? "Type your question..." : "Upload a PDF first"}
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  disabled={!pdfId || isSending} // Disable if no PDF or sending
                />
                <Button type="submit" disabled={!chatInput.trim() || isSending || !pdfId}>
                  {isSending ? "Sending..." : "Send"}
                </Button>
              </form>
            </CardFooter>
          </Card>
        </div>

      </div>
      {/* Display error messages */}
      {error && (
        <div className="fixed bottom-4 right-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded shadow-md" role="alert">
          <strong className="font-bold">Error: </strong>
          <span className="block sm:inline">{error}</span>
        </div>
      )}
    </main>
  );
}

// TODO: add ui improvements to button, visually show button press
// TODO: add loading states and progress indicators
// TODO: add error handling and user feedback
// TODO: add search functionality
// TODO: fix chat functionality



