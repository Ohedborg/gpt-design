import React from 'react';
export const ArgsContext = React.createContext(null);
export const useState = React.useState;
export function useArgs(){const c=React.useContext(ArgsContext);return [c.args,c.update,()=>c.update(c.initial)];}
