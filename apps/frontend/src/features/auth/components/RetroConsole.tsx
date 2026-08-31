import React, { useState } from "react";

interface RetroConsoleProps {
  onStart: () => void;
  isError: boolean;
  errorMessage: string | null;
}

// Only generate once
const generateStaticSnow = (count: number) => {
  let snow = "";
  for (let i = 0; i < count; i++) {
    const x = Math.floor(Math.random() * 3000) - 500;
    const y = Math.floor(Math.random() * 3000) - 1000;
    const color = i % 4 === 0 ? "#ffddaa" : "#ffffff";
    snow += `${x}px ${y}px ${color}${i < count - 1 ? ", " : ""}`;
  }
  return snow;
};

const snow1 = generateStaticSnow(300);
const snow2 = generateStaticSnow(150);
const snow3 = generateStaticSnow(50);

export const RetroConsole: React.FC<RetroConsoleProps> = ({
  onStart,
  isError,
  errorMessage,
}) => {
  const [activeButton, setActiveButton] = useState<string | null>(null);

  const handleStart = () => {
    setActiveButton("A");
    setTimeout(() => setActiveButton(null), 150);
    onStart();
  };

  return (
    <div className="relative w-full min-h-screen overflow-hidden bg-[linear-gradient(to_bottom,#100d28_0%,#351b3d_60%,#c25833_100%)] flex items-center justify-center p-4">
      {/* Twilight Window Falling Snow */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <div
          className="w-[2px] h-[2px] bg-transparent opacity-60"
          style={{
            boxShadow: snow1,
            animation: "falling-snow 40s linear infinite",
          }}
        />
        <div
          className="w-[3px] h-[3px] bg-transparent opacity-80"
          style={{
            boxShadow: snow2,
            animation: "falling-snow 30s linear infinite",
          }}
        />
        <div
          className="w-[4px] h-[4px] bg-transparent opacity-100"
          style={{
            boxShadow: snow3,
            animation: "falling-snow 20s linear infinite",
          }}
        />
      </div>

      {/* The Pixel Art Console Shell */}
      {/* Uses a stepped clip-path for blocky corners, and hard inset shadows for retro shading */}
      <div
        className="relative z-10 w-full max-w-[400px] bg-[#dfd6c8] pt-8 pb-12 px-6 flex flex-col items-center shadow-[16px_16px_0px_rgba(0,0,0,0.5)]"
        style={{
          clipPath:
            "polygon(8px 0, calc(100% - 8px) 0, 100% 8px, 100% calc(100% - 8px), calc(100% - 8px) 100%, 8px 100%, 0 calc(100% - 8px), 0 8px)",
          boxShadow:
            "inset -8px -8px 0px rgba(0,0,0,0.15), inset 8px 8px 0px rgba(255,255,255,0.6)",
        }}
      >
        {/* Screen Bezel - Flat dark grey, blocky corners */}
        <div
          className="w-full bg-[#3b3d45] pt-4 pb-6 px-4 relative flex flex-col items-center"
          style={{
            clipPath:
              "polygon(4px 0, calc(100% - 4px) 0, 100% 4px, 100% calc(100% - 4px), calc(100% - 4px) 100%, 4px 100%, 0 calc(100% - 4px), 0 4px)",
            boxShadow:
              "inset -4px -4px 0px rgba(0,0,0,0.4), inset 4px 4px 0px rgba(255,255,255,0.1)",
          }}
        >
          <div className="w-full flex justify-between px-2 mb-2 items-center">
            <div
              className="w-3 h-3 bg-red-500"
              style={{
                boxShadow:
                  "inset -1px -1px 0px #880000, inset 1px 1px 0px #ff8888",
              }}
            />
            <div className="text-[#a0a5b5] text-[10px] tracking-widest font-bold font-fell-sc">
              BATTERY
            </div>
          </div>

          {/* The Screen Display */}
          <div
            className="w-full aspect-[4/3] bg-[#8bac0f] relative overflow-hidden flex flex-col items-center justify-center animate-boot border-4 border-[#1c1d22]"
            style={{ boxShadow: "inset 6px 6px 0px rgba(0,0,0,0.3)" }}
          >
            {/* CRT Scanlines Overlay - Flat sharp lines */}
            <div className="absolute inset-0 pointer-events-none z-20 bg-[linear-gradient(rgba(0,0,0,0)_50%,rgba(0,0,0,0.15)_50%)] bg-[length:100%_4px] opacity-70 mix-blend-overlay" />

            {/* Screen Content */}
            <div className="relative z-10 w-full p-4 flex flex-col items-center text-[#0f380f] font-mono text-center">
              {isError ? (
                <div className="flex flex-col items-center space-y-4">
                  <h2 className="text-lg font-bold">GAME OVER</h2>
                  <p className="text-[10px] leading-tight break-words px-2">
                    {errorMessage}
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center space-y-6">
                  <h1 className="text-2xl leading-tight font-fell font-bold">
                    AI-DND
                  </h1>
                  <button
                    onClick={handleStart}
                    aria-label="Press Start to Login"
                    className="text-xs cursor-pointer focus:outline-none hover:text-[#306230] transition-colors font-fell-sc font-bold"
                  >
                    PRESS START
                  </button>
                </div>
              )}
            </div>
          </div>
          <div className="mt-4 text-[#a0a5b5] text-[10px] font-fell-sc tracking-widest">
            AI-DND
          </div>
        </div>

        {/* Controls Section */}
        <div className="w-full mt-12 flex justify-between px-2 relative">
          {/* Pixel D-Pad */}
          <div className="relative w-24 h-24">
            {/* Cross shape */}
            <div
              className="absolute top-1/3 left-0 w-full h-1/3 bg-[#2b2b2b]"
              style={{
                boxShadow:
                  "inset -4px -4px 0px rgba(0,0,0,0.5), inset 4px 4px 0px rgba(255,255,255,0.1)",
              }}
            />
            <div
              className="absolute top-0 left-1/3 w-1/3 h-full bg-[#2b2b2b]"
              style={{
                boxShadow:
                  "inset -4px -4px 0px rgba(0,0,0,0.5), inset 4px 4px 0px rgba(255,255,255,0.1)",
              }}
            />
            {/* Center dot */}
            <div className="absolute top-1/2 left-1/2 w-4 h-4 -mt-2 -ml-2 bg-[#111111]" />
          </div>

          {/* A / B Buttons */}
          <div className="flex space-x-6 items-end mb-4">
            <div className="flex flex-col items-center">
              <button
                className={`w-12 h-12 bg-[#9f2542] focus:outline-none transition-all ${activeButton === "B" ? "translate-y-1" : ""}`}
                style={{
                  clipPath:
                    "polygon(4px 0, calc(100% - 4px) 0, 100% 4px, 100% calc(100% - 4px), calc(100% - 4px) 100%, 4px 100%, 0 calc(100% - 4px), 0 4px)",
                  boxShadow:
                    activeButton === "B"
                      ? "inset -2px -2px 0px rgba(0,0,0,0.4), inset 2px 2px 0px rgba(255,255,255,0.2)"
                      : "inset -4px -6px 0px rgba(0,0,0,0.4), inset 4px 4px 0px rgba(255,255,255,0.2)",
                }}
                onClick={() => {
                  setActiveButton("B");
                  setTimeout(() => setActiveButton(null), 150);
                }}
                aria-label="B Button"
              />
              <span className="text-[#a49a8c] font-fell-sc mt-3 text-[10px]">
                B
              </span>
            </div>

            <div className="flex flex-col items-center -mt-8">
              <button
                className={`w-12 h-12 bg-[#9f2542] focus:outline-none transition-all ${activeButton === "A" ? "translate-y-1" : ""}`}
                style={{
                  clipPath:
                    "polygon(4px 0, calc(100% - 4px) 0, 100% 4px, 100% calc(100% - 4px), calc(100% - 4px) 100%, 4px 100%, 0 calc(100% - 4px), 0 4px)",
                  boxShadow:
                    activeButton === "A"
                      ? "inset -2px -2px 0px rgba(0,0,0,0.4), inset 2px 2px 0px rgba(255,255,255,0.2)"
                      : "inset -4px -6px 0px rgba(0,0,0,0.4), inset 4px 4px 0px rgba(255,255,255,0.2)",
                }}
                onClick={handleStart}
                aria-label="A Button"
              />
              <span className="text-[#a49a8c] font-fell-sc mt-3 text-[10px]">
                A
              </span>
            </div>
          </div>
        </div>

        {/* Select / Start Buttons */}
        <div className="w-full flex justify-center space-x-6 mt-8">
          <div className="flex flex-col items-center">
            <div
              className="w-14 h-4 bg-[#4d535b] transform -rotate-12"
              style={{
                clipPath:
                  "polygon(2px 0, calc(100% - 2px) 0, 100% 2px, 100% calc(100% - 2px), calc(100% - 2px) 100%, 2px 100%, 0 calc(100% - 2px), 0 2px)",
                boxShadow:
                  "inset -2px -4px 0px rgba(0,0,0,0.5), inset 2px 2px 0px rgba(255,255,255,0.2)",
              }}
            />
            <span className="text-[#a49a8c] font-fell-sc text-[8px] mt-3 tracking-widest">
              SELECT
            </span>
          </div>
          <div className="flex flex-col items-center">
            <div
              className="w-14 h-4 bg-[#4d535b] transform -rotate-12 cursor-pointer active:translate-y-1 transition-transform"
              onClick={handleStart}
              style={{
                clipPath:
                  "polygon(2px 0, calc(100% - 2px) 0, 100% 2px, 100% calc(100% - 2px), calc(100% - 2px) 100%, 2px 100%, 0 calc(100% - 2px), 0 2px)",
                boxShadow:
                  "inset -2px -4px 0px rgba(0,0,0,0.5), inset 2px 2px 0px rgba(255,255,255,0.2)",
              }}
            />
            <span className="text-[#a49a8c] font-fell-sc text-[8px] mt-3 tracking-widest">
              START
            </span>
          </div>
        </div>

        {/* Pixel Speaker Grill */}
        <div className="absolute bottom-6 right-6 flex space-x-2 transform -rotate-12">
          {[...Array(6)].map((_, i) => (
            <div
              key={i}
              className="w-2 h-14 bg-[#b8a99a]"
              style={{ boxShadow: "inset 2px 2px 0px rgba(0,0,0,0.2)" }}
            />
          ))}
        </div>
      </div>
    </div>
  );
};
