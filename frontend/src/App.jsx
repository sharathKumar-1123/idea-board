import { useEffect, useState } from "react";

const MAX_LENGTH = 500;

export default function App() {
  const [ideas, setIdeas] = useState([]);
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function loadIdeas() {
    try {
      const res = await fetch("/api/ideas");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setIdeas(await res.json());
      setError("");
    } catch (err) {
      setError(`Could not load ideas (${err.message}).`);
    }
  }

  useEffect(() => {
    loadIdeas();
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    const text = content.trim();
    if (!text) return;

    setSaving(true);
    try {
      const res = await fetch("/api/ideas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setContent("");
      await loadIdeas();
    } catch (err) {
      setError(`Could not save idea (${err.message}).`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="container">
      <h1>💡 Idea Board</h1>

      <form onSubmit={handleSubmit} className="idea-form">
        <input
          type="text"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Share a new idea…"
          maxLength={MAX_LENGTH}
          aria-label="New idea"
        />
        <button type="submit" disabled={saving || !content.trim()}>
          {saving ? "Saving…" : "Add idea"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {ideas.length === 0 && !error ? (
        <p className="empty">No ideas yet — be the first!</p>
      ) : (
        <ul className="idea-list">
          {ideas.map((idea) => (
            <li key={idea.id}>
              <p>{idea.content}</p>
              <time dateTime={idea.created_at}>{new Date(idea.created_at).toLocaleString()}</time>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
