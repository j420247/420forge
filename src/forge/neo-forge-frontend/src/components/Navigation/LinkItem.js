import React from 'react';
import { Link, Route } from 'react-router-dom';


export const LinkItem = ({ components: { Item }, to, ...props }: *) => {
    return (
      <Route
        render={({ location: { pathname } }) => (
          <Item
            component={({ children, className }) => (
              <Link className={className} to={to}>
                {children}
              </Link>
            )}
            isSelected={pathname === to}
            {...props}
          />
        )}
      />
    );
  };