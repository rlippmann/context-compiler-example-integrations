export default function HomePage() {
  return (
    <main
      style={{
        maxWidth: 760,
        margin: "0 auto",
        minHeight: "100vh",
        padding: "64px 24px",
        display: "grid",
        gap: 20,
        alignContent: "center"
      }}
    >
      <p style={{ margin: 0, letterSpacing: "0.14em", textTransform: "uppercase", fontSize: 12 }}>
        Context Compiler example
      </p>
      <h1 style={{ margin: 0, fontSize: "clamp(2.5rem, 8vw, 4.75rem)", lineHeight: 0.95 }}>
        Next.js starter with drafter
      </h1>
      <p style={{ margin: 0, fontSize: 18, lineHeight: 1.6 }}>
        This variant keeps the useful part on the server. POST a chat payload to <code>/api/chat</code> and the
        route will restore authoritative state, optionally validate drafted directive input, and return the request
        payload the host would send onward.
      </p>
      <pre
        style={{
          margin: 0,
          padding: 20,
          overflowX: "auto",
          border: "1px solid #b8aa92",
          background: "#fffaf2",
          fontSize: 14
        }}
      >
        {`curl -X POST http://localhost:3000/api/chat \\
  -H 'content-type: application/json' \\
  -d '{"sessionId":"demo","input":"keep replies concise"}'`}
      </pre>
    </main>
  );
}
