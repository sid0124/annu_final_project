import React from 'react';
import { createStore, combineReducers, applyMiddleware } from 'redux';
import createSagaMiddleware from 'redux-saga';
import { composeWithDevTools } from 'redux-devtools-extension';
import { persistStore, persistReducer } from 'redux-persist';
import storage from 'redux-persist/lib/storage';

import api from '../services/api';
import rootSaga from '../sagas';
import rootReducer from '../reducers';

// Persistence config
const persistConfig = {
  key: 'root',
  storage,
  whitelist: ['user', 'tokens'],
};

// Reducers
const persistedReducer = persistReducer(persistConfig, rootReducer);

// Saga middleware
const sagaMiddleware = createSagaMiddleware();

// Store
export const store = createStore(
  persistedReducer,
  composeWithDevTools(applyMiddleware(sagaMiddleware))
);

export const persistor = persistStore(store);

// Run sagas
sagaMiddleware.run(rootSaga);

// Root component
const Root = () => {
  return <></>;
};

export default Root;