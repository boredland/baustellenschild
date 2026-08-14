/**
 * The marker for a permit, drawn as the thing it marks: a construction sign on
 * two posts. Far out these stay plain cadastral dots; from z15 the board unfolds,
 * so zooming in is the same move as walking up to the fence and reading it.
 */

const WIDTH = 34;
const HEIGHT = 30;
const RATIO = 2;

const SCHILD = "#fbfbf7";
const INK = "#14140f";
const GELB = "#fcbb0a";
const POST = "#9a9c93";

export function signImage({ selected = false } = {}) {
  const canvas = document.createElement("canvas");
  canvas.width = WIDTH * RATIO;
  canvas.height = HEIGHT * RATIO;

  const context = canvas.getContext("2d");
  context.scale(RATIO, RATIO);

  const boardWidth = 26;
  const boardHeight = 18;
  const left = (WIDTH - boardWidth) / 2;

  context.fillStyle = POST;
  context.fillRect(left + 4, boardHeight - 2, 1.6, HEIGHT - boardHeight);
  context.fillRect(left + boardWidth - 5.6, boardHeight - 2, 1.6, HEIGHT - boardHeight);

  context.fillStyle = selected ? GELB : SCHILD;
  context.fillRect(left, 1, boardWidth, boardHeight);

  if (!selected) {
    context.fillStyle = GELB;
    context.fillRect(left, 1, boardWidth, 3.2);
  }

  context.strokeStyle = INK;
  context.lineWidth = selected ? 2 : 1;
  context.strokeRect(left + 0.5, 1.5, boardWidth - 1, boardHeight - 1);

  // Three ruled lines: Bauvorhaben, Bauherr, Entwurfsverfasser.
  context.fillStyle = INK;
  context.globalAlpha = selected ? 0.8 : 0.65;
  for (let i = 0; i < 3; i += 1) {
    const width = [16, 12, 14][i];
    context.fillRect(left + 4, 8 + i * 3.4, width, 1.2);
  }
  context.globalAlpha = 1;

  const image = context.getImageData(0, 0, canvas.width, canvas.height);
  return { width: canvas.width, height: canvas.height, data: image.data };
}
