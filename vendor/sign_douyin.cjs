// Calls the original R-plugin signing helper. No cookies are passed to this process.
const { generate_a_bogus } = require('./a-bogus.cjs');
const [query, userAgent] = process.argv.slice(2);
if (!query || !userAgent || query.length > 8192 || userAgent.length > 1024) {
  process.exit(2);
}
process.stdout.write(generate_a_bogus(query, userAgent));
