import { Notyf } from 'notyf';

import { ResponseStatus } from '../types';

let notyf: Notyf | undefined;

export async function notify(response: ResponseStatus) {
  if (notyf == null) {
    const Notyf = await import('notyf');
    notyf = new Notyf.Notyf({
      position: { x: 'center', y: 'bottom' },
      duration: 3000,
    });
  }

  if (response.success) {
    notyf.success(response.message);
  } else {
    notyf.error(response.message);
  }
}
