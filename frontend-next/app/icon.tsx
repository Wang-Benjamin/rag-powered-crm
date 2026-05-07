import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

export const size = { width: 512, height: 512 };
export const contentType = "image/png";

const DEEP = "#191B23";
const BONE = "#FBFAF5";

export default async function Icon() {
  const font = await readFile(join(process.cwd(), "app/InstrumentSerif-Regular.ttf"));

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: DEEP,
          color: BONE,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "Instrument Serif",
        }}
      >
        <div
          style={{
            fontSize: 440,
            lineHeight: 1,
            transform: "translate(3%, 2%)",
          }}
        >
          P
        </div>
      </div>
    ),
    {
      ...size,
      fonts: [{ name: "Instrument Serif", data: font, weight: 400, style: "normal" }],
    },
  );
}
