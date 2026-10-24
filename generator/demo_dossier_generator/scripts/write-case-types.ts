import { OUT_DIR, writeCaseTypes } from "./caseTypes";

const written = await writeCaseTypes();
console.log(`wrote ${written.join(", ")} to ${OUT_DIR}`);
