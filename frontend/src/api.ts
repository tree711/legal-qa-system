import axios from 'axios'
export type Role='user'|'assistant'|'system'
export interface Message{role:Role;content:string}
export interface Reference{law_name:string;article_no:string;content:string;chapter?:string;source_url?:string;score:number}
export interface ChatResponse{answer:string;messages:Message[];references:Reference[];model:string;elapsed_seconds:number;low_confidence:boolean;rewritten_question?:string;steps?:string[];summary_result?:{summary?:string};retrieval_result?:unknown}
export interface RagResponse{answer:string;references:Reference[];model:string;elapsed_seconds:number;low_confidence:boolean}
const api=axios.create({baseURL:import.meta.env.VITE_API_BASE_URL||'/api',timeout:180000})
export async function health(){return (await api.get('/health')).data}
export async function rag(prompt:string,top_k:number){return (await api.post<RagResponse>('/rag',{prompt,top_k})).data}
export async function chat(messages:Message[],top_k:number,use_rag:boolean){return (await api.post<ChatResponse>('/chat',{messages,top_k,use_rag})).data}
export async function searchLaw(query:string,top_k:number){return (await api.post('/search',{query,top_k})).data}
