(()=>{const g=typeof self!=='undefined'?self:window;
const ss=()=>({e:{label:'Light AF',cap:5,dmgPerLevel:.012},v:{label:'Void AF',cap:5,dmgPerLevel:.011},c:{label:'Chaos Fusion',cap:10,dmgPerLevel:.010},x:{label:'Xeno Transmute',cap:13,dmgPerLevel:.014}});
const af=()=>({star:{label:'Astral Forge',cap:3,dmgPerLevel:.004}});
const it=(slot,tier,priority,paths,note)=>({slot:slot,rarity:tier,maxLevel:230,priority:priority,paths:paths,ss:tier==='ss',afCap:tier==='ss'?null:3,note:note||''});
g.SIO_ITEMS={
'Twin Lance':it('Weapon','ss',100,ss(),'SS Weapon / Starforged Havoc'),
'Judgment Necklace':it('Necklace','ss',62,ss(),'SS Necklace'),
'Moonscar Bracer':it('Gloves','ss',88,ss(),'SS Gloves'),
'Evervoid Armor':it('Armor','ss',45,ss(),'SS Armor'),
'Stardust Sash':it('Belt','ss',92,ss(),'SS Belt'),
'Glacial Warboots':it('Boots','ss',94,ss(),'SS Boots'),
'Eternal Suit':it('Armor','s',78,af(),'All-round armor after Armor of Quietus'),
'Voidwaker Emblem':it('Necklace','s',80,af(),'Strong practical necklace before SS Necklace'),
'Twisting Belt':it('Belt','s',75,af(),'Good damage belt before SS Belt'),
'Voidwaker Handguards':it('Gloves','s',82,af(),'Strong glove before SS Gloves'),
'Voidwaker Treads':it('Boots','s',82,af(),'Strong boots before SS Boots'),
'Armor of Quietus':it('Armor','s',90,af(),'Rush red for chapters and AFK'),
'Void Power':it('Weapon','s',70,af(),'Early and mid-game crowd control'),
'Light Runners':it('Boots','normal',45,af(),'Good early boots'),
'Stylish Belt':it('Belt','normal',50,af(),'Good early wave belt'),
'Fingerless Gloves':it('Gloves','normal',45,af(),'Good early gloves'),
'Metal Neckguard':it('Necklace','normal',35,af(),'Useful chapter survival necklace')
};})();
