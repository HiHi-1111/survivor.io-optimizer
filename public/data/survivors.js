(function(){
  var g=typeof self!=='undefined'?self:window;
  function survivor(group){return{group:group||'confirmed source name',maxLevel:6,dmgPerLevel:0,sourceStatus:'confirmed_name_only'}}
  g.SIO_SURVIVORS={
    'Master Yang':survivor('S survivor'),
    'King':survivor('standard survivor'),
    'Tsukuyomi':survivor('standard survivor'),
    'Worm':survivor('standard survivor'),
    'Wesson':survivor('standard survivor'),
    'SpongeBob':survivor('SP/event survivor'),
    'Squidward':survivor('SP/event survivor'),
    'Patrick':survivor('SP/event survivor'),
    'Sandy':survivor('SP/event survivor'),
    'Raphael':survivor('TMNT/SP survivor'),
    'Leonardo':survivor('TMNT/SP survivor'),
    'April':survivor('TMNT/SP survivor'),
    'Michelangelo':survivor('TMNT/SP survivor'),
    'Donatello':survivor('TMNT/SP survivor'),
    'Splinter':survivor('TMNT/SP survivor')
  };
})();
