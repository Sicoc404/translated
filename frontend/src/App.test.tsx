import React from 'react';

export default function TestApp() {
  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(to bottom right, #7e22ce, #6d28d9, #5b21b6)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'white',
      fontFamily: 'Arial, sans-serif'
    }}>
      <div style={{
        background: 'rgba(255, 255, 255, 0.1)',
        padding: '2rem',
        borderRadius: '1rem',
        textAlign: 'center',
        maxWidth: '600px'
      }}>
        <h1 style={{ fontSize: '3rem', marginBottom: '1rem' }}>Pryme+</h1>
        <p style={{ fontSize: '1.2rem', marginBottom: '2rem' }}>测试页面 - 如果您看到这个页面，React正在正常工作！</p>
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: '1rem',
          marginTop: '2rem'
        }}>
          <div style={{
            background: 'white',
            color: '#333',
            padding: '1rem',
            borderRadius: '0.5rem',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🇰🇷</div>
            <div>韩语</div>
          </div>
          <div style={{
            background: 'white',
            color: '#333',
            padding: '1rem',
            borderRadius: '0.5rem',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🇯🇵</div>
            <div>日语</div>
          </div>
          <div style={{
            background: 'white',
            color: '#333',
            padding: '1rem',
            borderRadius: '0.5rem',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🇻🇳</div>
            <div>越南语</div>
          </div>
          <div style={{
            background: 'white',
            color: '#333',
            padding: '1rem',
            borderRadius: '0.5rem',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🇲🇾</div>
            <div>马来语</div>
          </div>
        </div>
      </div>
    </div>
  );
} 