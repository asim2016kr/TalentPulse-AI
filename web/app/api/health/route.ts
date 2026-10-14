import {json} from '../../../lib/response';
// Liveness only: deliberately does not reveal database or provider configuration.
export function GET() {return json({status:'ok'});}
