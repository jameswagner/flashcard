import '@testing-library/jest-dom';
import { TextDecoder, TextEncoder } from 'util';
import { fetch, Request, Response, Headers } from 'cross-fetch';

// Add browser globals
global.fetch = fetch;
global.Request = Request;
global.Response = Response;
global.Headers = Headers;
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder; 