import { config } from 'dotenv';
import { resolve } from 'node:path';
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
config({path:resolve(process.cwd(),'../.env'),quiet:true});
const command=process.argv[2];
if (!['dev','start'].includes(command)) throw new Error('Invalid server command');
const cli=createRequire(import.meta.url).resolve('next/dist/bin/next');
const child=spawn(process.execPath,[cli,command,'--hostname','127.0.0.1','--port','3000'],{
  stdio:'inherit',env:process.env,windowsHide:true
});
for(const signal of ['SIGINT','SIGTERM']) process.on(signal,()=>child.kill(signal));
child.on('exit',code=>process.exit(code ?? 1));
