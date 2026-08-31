import React, { useState } from "react";
import { useStudioStore } from "../../stores/studio.store";

// Mock extracted data
const MOCK_ENTITIES = [
  { id: 1, name: "The Crimson Guild", type: "Faction", desc: "Ruthless mercenaries." },
  { id: 2, name: "Elara", type: "Character", desc: "The last elf mage." }
];

const MOCK_FACTS = [
  { id: 1, text: "The Crimson Guild is hunting Elara." },
  { id: 2, text: "Elyria was forged in dragonfire." }
];

export const Step4Review: React.FC = () => {
  const { newbieDraft } = useStudioStore();
  const [entities, setEntities] = useState(MOCK_ENTITIES);
  const [facts, setFacts] = useState(MOCK_FACTS);
  const [isPublishing, setIsPublishing] = useState(false);

  const handlePublish = () => {
    setIsPublishing(true);
    // Simulate API call
    setTimeout(() => {
      setIsPublishing(false);
      alert("Successfully published! (Mock)");
    }, 2000);
  };

  return (
    <div className="space-y-8 pb-32">
      <div className="space-y-2 border-b border-zinc-800 pb-4">
        <h2 className="text-2xl font-semibold text-zinc-100 tracking-tight">Review & Publish</h2>
        <p className="text-sm text-zinc-400">Review the entities and facts extracted from your lore. You can edit them below.</p>
      </div>

      <div className="space-y-6">
        <h3 className="text-sm font-semibold tracking-wide text-zinc-300 uppercase border-b border-zinc-800 pb-2">Extracted Entities</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {entities.map(e => (
            <div key={e.id} className="bg-zinc-950 border border-zinc-800 p-4 space-y-3">
              <div className="flex gap-2">
                <input 
                  type="text" 
                  value={e.name} 
                  onChange={(ev) => setEntities(entities.map(en => en.id === e.id ? { ...en, name: ev.target.value } : en))}
                  className="flex-1 bg-transparent border-b border-zinc-800 rounded-none px-2 py-1 text-sm font-semibold text-zinc-100 focus:outline-none focus:border-zinc-400"
                />
                <input 
                  type="text" 
                  value={e.type} 
                  onChange={(ev) => setEntities(entities.map(en => en.id === e.id ? { ...en, type: ev.target.value } : en))}
                  className="w-24 bg-transparent border-b border-zinc-800 rounded-none px-2 py-1 text-xs font-semibold uppercase tracking-wider text-zinc-400 focus:outline-none focus:border-zinc-400 text-center"
                />
              </div>
              <textarea
                value={e.desc}
                onChange={(ev) => setEntities(entities.map(en => en.id === e.id ? { ...en, desc: ev.target.value } : en))}
                className="w-full h-16 bg-zinc-900 border border-zinc-800 rounded-none px-3 py-2 text-sm font-sans text-zinc-300 focus:outline-none focus:border-zinc-400 resize-none"
              />
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-6">
        <h3 className="text-sm font-semibold tracking-wide text-zinc-300 uppercase border-b border-zinc-800 pb-2">Extracted Facts</h3>
        <div className="space-y-3">
          {facts.map(f => (
            <div key={f.id} className="bg-zinc-950 border border-zinc-800 p-3">
              <input 
                type="text" 
                value={f.text} 
                onChange={(ev) => setFacts(facts.map(fa => fa.id === f.id ? { ...fa, text: ev.target.value } : fa))}
                className="w-full bg-transparent rounded-none px-3 py-1 text-sm font-sans text-zinc-300 focus:outline-none focus:border-b focus:border-zinc-400"
              />
            </div>
          ))}
        </div>
      </div>

      <div className="pt-8 flex justify-end">
        <button 
          onClick={handlePublish}
          disabled={isPublishing}
          className="px-8 py-3 bg-zinc-100 hover:bg-white text-zinc-950 font-semibold rounded-none transition-colors flex items-center gap-2 uppercase tracking-wider text-sm"
        >
          {isPublishing ? (
            <>
              <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-zinc-950"></span>
              Publishing...
            </>
          ) : (
            "Publish Scenario"
          )}
        </button>
      </div>
    </div>
  );
};
