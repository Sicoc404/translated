import React from 'react';

export default function TestApp() {
  const containerStyle: React.CSSProperties = {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #7e22ce 0%, #6d28d9 50%, #5b21b6 100%)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'white',
    fontFamily: 'Arial, sans-serif',
    padding: '20px',
    boxSizing: 'border-box'
  };

  const cardContainerStyle: React.CSSProperties = {
    background: 'rgba(255, 255, 255, 0.1)',
    padding: '32px',
    borderRadius: '16px',
    textAlign: 'center',
    maxWidth: '800px',
    width: '100%',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)'
  };

  const titleStyle: React.CSSProperties = {
    fontSize: '48px',
    marginBottom: '16px',
    fontWeight: 'bold'
  };

  const subtitleStyle: React.CSSProperties = {
    fontSize: '20px',
    marginBottom: '32px'
  };

  const gridStyle: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
    gap: '16px',
    marginTop: '32px'
  };

  const languageCardStyle: React.CSSProperties = {
    background: 'white',
    color: '#333',
    padding: '20px',
    borderRadius: '12px',
    textAlign: 'center',
    boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
    cursor: 'pointer',
    transition: 'transform 0.2s ease'
  };

  const flagStyle: React.CSSProperties = {
    fontSize: '32px',
    marginBottom: '8px',
    display: 'block'
  };

  const languageNameStyle: React.CSSProperties = {
    fontSize: '16px',
    fontWeight: 'bold'
  };

  return (
    <div style={containerStyle}>
      <div style={cardContainerStyle}>
        <h1 style={titleStyle}>Pryme+</h1>
        <p style={subtitleStyle}>测试页面 - React样式测试</p>
        
        <div style={gridStyle}>
          <div style={languageCardStyle}>
            <span style={flagStyle}>🇰🇷</span>
            <div style={languageNameStyle}>韩语</div>
            <div style={{fontSize: '12px', color: '#666', marginTop: '4px'}}>한국어</div>
          </div>
          <div style={languageCardStyle}>
            <span style={flagStyle}>🇯🇵</span>
            <div style={languageNameStyle}>日语</div>
            <div style={{fontSize: '12px', color: '#666', marginTop: '4px'}}>日本語</div>
          </div>
          <div style={languageCardStyle}>
            <span style={flagStyle}>🇻🇳</span>
            <div style={languageNameStyle}>越南语</div>
            <div style={{fontSize: '12px', color: '#666', marginTop: '4px'}}>Tiếng Việt</div>
          </div>
          <div style={languageCardStyle}>
            <span style={flagStyle}>🇲🇾</span>
            <div style={languageNameStyle}>马来语</div>
            <div style={{fontSize: '12px', color: '#666', marginTop: '4px'}}>Bahasa Melayu</div>
          </div>
        </div>
        
        <div style={{marginTop: '32px', fontSize: '14px', color: 'rgba(255, 255, 255, 0.8)'}}>
          如果您看到四个白色卡片整齐排列，那么样式系统工作正常！
        </div>
      </div>
    </div>
  );
} 
