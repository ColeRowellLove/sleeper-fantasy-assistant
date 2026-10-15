// Shared by the server layout and the client toggle. This must NOT be a "use client" module:
// importing a non-component export from one into a server component gives undefined.

export const THEME_KEY = "sa_theme";

/**
 * Inline script that runs before first paint so a saved theme choice never flashes the wrong
 * colors. It only ever applies "light" or "dark".
 */
export const THEME_INIT = `try{var t=localStorage.getItem(${JSON.stringify(THEME_KEY)});if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;
