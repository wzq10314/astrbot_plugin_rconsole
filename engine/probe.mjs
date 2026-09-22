import fs from 'node:fs';
const pkg=JSON.parse(fs.readFileSync(new URL('./package.json',import.meta.url),'utf8'));
try {
 for(const name of Object.keys(pkg.dependencies)) await import(name);
 process.exit(0);
} catch {
 process.exit(1);
}
