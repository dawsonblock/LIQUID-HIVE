import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ChatPanel from './ChatPanel';
import { Provider } from 'react-redux';
import { store } from '../../store';

jest.mock('../services/api', () => ({
  postChat: async () => ({ answer: 'Hello World' }),
  fetchState: async () => ({ operator_intent: 'Answering' }),
  postVision: async () => ({ answer: 'This is an image.' })
}));

const renderWithProviders = (ui: React.ReactElement) => render(<Provider store={store}>{ui}</Provider>);

test('renders chat input and sends a message', async () => {
  renderWithProviders(<ChatPanel />);
  const input = screen.getByPlaceholderText(/type a message/i);
  fireEvent.change(input, { target: { value: 'Hello' } });
  fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });
  expect(await screen.findByText('Hello World')).toBeInTheDocument();
});

// New vision test

test('sends an image when a file is selected', async () => {
  renderWithProviders(<ChatPanel />);
  const file = new File(['(⌐□_□)'], 'chucknorris.png', { type: 'image/png' });
  const fileInput = screen.getByLabelText(/attach file/i);
  
  // Simulate file upload
  fireEvent.change(fileInput, { target: { files: [file] } });
  
  const sendImageButton = screen.getByRole('button', { name: /send image/i });
  fireEvent.click(sendImageButton);

  expect(await screen.findByText('This is an image.')).toBeInTheDocument();
});