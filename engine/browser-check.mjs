import {checkBrowser} from './browser-runtime.mjs';
const result=await checkBrowser();
console.log(JSON.stringify(result));
process.exit(result.ok?0:1);
