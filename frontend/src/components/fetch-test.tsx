'use client'

import { useState, useEffect } from 'react'

export default function FetchTest() {
    const [message, setMessage] = useState("Waiting for response...")

    useEffect(() => {
        fetch("http://127.0.0.1:5000")
            .then((res) => res.json())
            .then((data) => setMessage(data.message))
            .catch((err) => setMessage("Error fetching data"))
    }, [])

    return (
        <div>
            <h1>{message}</h1>
        </div>
    )
}